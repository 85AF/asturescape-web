// frontend/src/App.tsx
import React, { useState, useEffect, useCallback } from 'react';
import axios from 'axios';
import { websocketService } from './services/websocketService';
import type { JobProgressMessage } from './services/websocketService'; // Type-only import
import { JobStatus } from './types'; // JobStatus is used as a value
import type { Job } from './types'; // Type-only import

// Helper to get API URL (useful if API is on different port during dev)
const API_BASE_URL = '/api'; // Adjust if your Nginx proxies to a different path or if backend is elsewhere

function App() {
    const [selectedFile, setSelectedFile] = useState<File | null>(null);
    const [uploading, setUploading] = useState(false);
    const [uploadProgress, setUploadProgress] = useState(0);
    const [currentJob, setCurrentJob] = useState<Job | null>(null);
    const [jobs, setJobs] = useState<Job[]>([]); // For listing jobs
    const [wsError, setWsError] = useState<string | null>(null);

    const fetchJobs = useCallback(async () => {
        try {
            const response = await axios.get<Job[]>(`${API_BASE_URL}/jobs/`);
            // Sort jobs by creation date, newest first
            const sortedJobs = response.data.sort((a, b) =>
                new Date(b.created_at).getTime() - new Date(a.created_at).getTime()
            );
            setJobs(sortedJobs);
        } catch (error) {
            console.error('Error fetching jobs:', error);
            // Handle error display for job fetching if needed
        }
    }, []);

    useEffect(() => {
        fetchJobs(); // Fetch jobs on initial load
    }, [fetchJobs]);

    const handleFileChange = (event: React.ChangeEvent<HTMLInputElement>) => {
        if (event.target.files && event.target.files[0]) {
            setSelectedFile(event.target.files[0]);
            setCurrentJob(null); // Reset current job view on new file selection
            setWsError(null); // Clear previous WebSocket errors
        }
    };

    const handleUpload = async () => {
        if (!selectedFile) return;

        setUploading(true);
        setUploadProgress(0);
        setCurrentJob(null);
        setWsError(null);

        const formData = new FormData();
        formData.append('file', selectedFile);

        try {
            const response = await axios.post<Job>(`${API_BASE_URL}/jobs/`, formData, {
                headers: {
                    'Content-Type': 'multipart/form-data',
                },
                onUploadProgress: (progressEvent) => {
                    if (progressEvent.total) {
                        const percentCompleted = Math.round(
                            (progressEvent.loaded * 100) / progressEvent.total
                        );
                        setUploadProgress(percentCompleted);
                    }
                },
            });

            const newJob = response.data;
            console.log('Upload successful, job created:', newJob);
            setUploading(false);

            setJobs(prevJobs => [newJob, ...prevJobs].sort((a, b) =>
                new Date(b.created_at).getTime() - new Date(a.created_at).getTime()
            ));

            setCurrentJob({ ...newJob, progress: 0, current_message: 'Waiting for server...' });

            websocketService.connect(
                newJob.id,
                (data: JobProgressMessage) => {
                    console.log('Job update received via WebSocket:', data);
                    setWsError(null); // Clear any previous WS error on new message
                    setCurrentJob((prevJob) => {
                        if (prevJob && prevJob.id === newJob.id) {
                            return {
                                ...prevJob,
                                status: data.status,
                                progress: data.progress !== undefined ? data.progress : (data.status === JobStatus.COMPLETED ? 100 : prevJob.progress),
                                current_message: data.message || data.status,
                                result_txt_path: data.txt_path || prevJob.result_txt_path,
                                result_srt_path: data.srt_path || prevJob.result_srt_path,
                                duration_seconds: data.duration || prevJob.duration_seconds,
                                error_message: data.error || (data.status === JobStatus.FAILED ? data.message : prevJob.error_message),
                                updated_at: new Date().toISOString(), // Update timestamp on any message
                            };
                        }
                        return prevJob;
                    });
                    setJobs(prevJobsList => prevJobsList.map(job =>
                        job.id === newJob.id ? {
                            ...job,
                            status: data.status,
                            progress: data.progress !== undefined ? data.progress : (data.status === JobStatus.COMPLETED ? 100 : job.progress),
                            current_message: data.message || data.status,
                            result_txt_path: data.txt_path || job.result_txt_path,
                            result_srt_path: data.srt_path || job.result_srt_path,
                            duration_seconds: data.duration || job.duration_seconds,
                            error_message: data.error || (data.status === JobStatus.FAILED ? data.message : job.error_message),
                            updated_at: new Date().toISOString(),
                        } : job
                    ));
                },
                (errorEvent) => {
                    console.error('WebSocket error for job', newJob.id, errorEvent);
                    const errorMsg = 'WebSocket connection error. Status updates may not be real-time.';
                    setCurrentJob((prevJob) => prevJob && prevJob.id === newJob.id ? { ...prevJob, current_message: errorMsg } : prevJob);
                    setWsError(errorMsg);
                },
                (closeEvent) => {
                    console.log('WebSocket closed for job', newJob.id, `Code: ${closeEvent.code}, Reason: ${closeEvent.reason}, WasClean: ${closeEvent.wasClean}`);
                    setCurrentJob((prevJob) => {
                        if (prevJob && prevJob.id === newJob.id && prevJob.status !== JobStatus.COMPLETED && prevJob.status !== JobStatus.FAILED) {
                            return { ...prevJob, current_message: `WebSocket disconnected. Code: ${closeEvent.code}` };
                        }
                        return prevJob;
                    });
                     if (closeEvent.code !== 1000 && closeEvent.code !== 1001) { // 1001 is going away
                        setWsError(`WebSocket connection closed unexpectedly (Code: ${closeEvent.code}). Attempting to reconnect...`);
                    }
                }
            );

        } catch (error) {
            console.error('Error uploading file:', error);
            setUploading(false);
            const errorMsg = axios.isAxiosError(error) && error.response ? error.response.data.detail || error.message : 'An unknown error occurred during upload.';
            setCurrentJob({
                id: Date.now(), // Temporary ID for display
                filename: selectedFile.name,
                status: JobStatus.FAILED,
                created_at: new Date().toISOString(),
                updated_at: new Date().toISOString(),
                current_message: `Upload failed: ${errorMsg}`,
                error_message: errorMsg
            });
        }
    };

    useEffect(() => {
        return () => {
            console.log("App component unmounting, closing WebSocket if active.");
            websocketService.close();
        };
    }, []);

    const getDownloadUrl = (filePath?: string) => {
        if (!filePath) return '#';
        // Assuming backend serves files from root, e.g. /transcription_results/file.txt
        // Adjust if you have a specific static file serving endpoint or CDN
        return `/${filePath}`;
    }

    return (
        <div className="container mx-auto p-4">
            <h1 className="text-2xl font-bold mb-6 text-center text-gray-700">Audio Transcription Service</h1>

            <div className="mb-8 p-6 bg-white rounded-lg shadow-md">
                <h2 className="text-xl font-semibold mb-3 text-gray-800">Upload Audio File</h2>
                <input
                    type="file"
                    accept=".mp3,.wav,.m4a,.ogg" // Accept more audio types
                    onChange={handleFileChange}
                    className="mb-3 block w-full text-sm text-slate-500
                               file:mr-4 file:py-2 file:px-4
                               file:rounded-full file:border-0
                               file:text-sm file:font-semibold
                               file:bg-violet-50 file:text-violet-700
                               hover:file:bg-violet-100"
                />
                {selectedFile && <p className="text-sm text-gray-600 mb-3">Selected: {selectedFile.name}</p>}
                <button
                    onClick={handleUpload}
                    disabled={!selectedFile || uploading}
                    className="w-full px-4 py-2 bg-blue-600 text-white rounded-md hover:bg-blue-700 disabled:bg-gray-400 transition duration-150 ease-in-out"
                >
                    {uploading ? `Uploading (${uploadProgress}%)` : 'Upload and Transcribe'}
                </button>
                {wsError && <p className="text-sm text-red-500 mt-2">{wsError}</p>}
            </div>

            {currentJob && (
                <div className="mb-8 p-6 border border-gray-200 rounded-lg shadow-md bg-white">
                    <h3 className="text-lg font-semibold text-gray-800">Current Job Details</h3>
                    <p><strong>File:</strong> {currentJob.filename}</p>
                    <p><strong>ID:</strong> {currentJob.id}</p>
                    <p><strong>Status:</strong> <span className={`font-medium ${
                        currentJob.status === JobStatus.COMPLETED ? 'text-green-600' :
                        currentJob.status === JobStatus.FAILED ? 'text-red-600' :
                        currentJob.status === JobStatus.PROCESSING ? 'text-yellow-600' : 'text-gray-600'
                    }`}>{currentJob.status}</span></p>
                    {currentJob.status === JobStatus.PROCESSING && currentJob.progress !== undefined && (
                        <div className="w-full bg-gray-200 rounded-full h-2.5 my-2 dark:bg-gray-700">
                            <div className="bg-blue-600 h-2.5 rounded-full" style={{ width: `${currentJob.progress}%` }}></div>
                        </div>
                    )}
                    {currentJob.current_message && <p className="text-sm text-gray-700"><strong>Message:</strong> {currentJob.current_message}</p>}
                    {currentJob.status === JobStatus.COMPLETED && (
                        <div className="mt-2">
                            <p><strong>Duration:</strong> {currentJob.duration_seconds?.toFixed(2)}s</p>
                            {currentJob.result_txt_path && (
                                <a href={getDownloadUrl(currentJob.result_txt_path)} target="_blank" rel="noopener noreferrer" download className="text-blue-500 hover:underline mr-4">Download TXT</a>
                            )}
                            {currentJob.result_srt_path && (
                                <a href={getDownloadUrl(currentJob.result_srt_path)} target="_blank" rel="noopener noreferrer" download className="text-blue-500 hover:underline">Download SRT</a>
                            )}
                        </div>
                    )}
                    {currentJob.status === JobStatus.FAILED && currentJob.error_message && (
                         <p className="text-sm text-red-700"><strong>Error:</strong> {currentJob.error_message}</p>
                    )}
                    <p className="text-xs text-gray-500 mt-1">Last updated: {new Date(currentJob.updated_at).toLocaleString()}</p>
                </div>
            )}

            <div className="mt-8">
                <div className="flex justify-between items-center mb-3">
                    <h2 className="text-xl font-semibold text-gray-800">Transcription Jobs</h2>
                    <button
                        onClick={fetchJobs}
                        disabled={uploading}
                        className="px-4 py-2 text-sm bg-indigo-500 text-white rounded-md hover:bg-indigo-600 disabled:bg-gray-400 transition duration-150 ease-in-out"
                    >
                        Refresh List
                    </button>
                </div>
                {jobs.length === 0 ? <p className="text-gray-600">No jobs found. Upload a file to start.</p> : (
                    <ul className="space-y-4">
                        {jobs.map(job => (
                            <li key={job.id} className="p-4 border border-gray-200 rounded-lg shadow-sm bg-white">
                                <p className="font-medium text-gray-700">{job.filename} (ID: {job.id})</p>
                                <p className="text-sm">Status: <span className={`font-semibold ${
                                    job.status === JobStatus.COMPLETED ? 'text-green-600' :
                                    job.status === JobStatus.FAILED ? 'text-red-600' :
                                    job.status === JobStatus.PROCESSING ? 'text-yellow-600' : 'text-gray-600'
                                }`}>{job.status}</span></p>
                                {job.status === JobStatus.PROCESSING && job.progress !== undefined && job.id === currentJob?.id && (
                                    <div className="w-full bg-gray-200 rounded-full h-1.5 my-1 dark:bg-gray-700">
                                        <div className="bg-blue-500 h-1.5 rounded-full" style={{ width: `${job.progress}%` }}></div>
                                    </div>
                                )}
                                {job.current_message && job.id === currentJob?.id && <p className="text-xs text-gray-600 italic">Update: {job.current_message}</p>}
                                {job.status === JobStatus.COMPLETED && (
                                    <div className="mt-1">
                                        {job.result_txt_path && <a href={getDownloadUrl(job.result_txt_path)} target="_blank" rel="noopener noreferrer" download className="text-xs text-blue-500 hover:underline mr-2">Download TXT</a>}
                                        {job.result_srt_path && <a href={getDownloadUrl(job.result_srt_path)} target="_blank" rel="noopener noreferrer" download className="text-xs text-blue-500 hover:underline">Download SRT</a>}
                                    </div>
                                )}
                                 {job.status === JobStatus.FAILED && job.error_message && (
                                    <p className="text-xs text-red-700 mt-1">Error: {job.error_message}</p>
                                )}
                                <p className="text-xs text-gray-500 mt-1">Created: {new Date(job.created_at).toLocaleString()}</p>
                                <p className="text-xs text-gray-500">Last Updated: {new Date(job.updated_at).toLocaleString()}</p>
                            </li>
                        ))}
                    </ul>
                )}
            </div>
        </div>
    );
}

export default App;
