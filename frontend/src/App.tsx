// frontend/src/App.tsx
import React, { useState, useEffect, useCallback, useRef } from 'react';
import axios, { AxiosError } from 'axios'; // Added AxiosError
import { websocketService } from './services/websocketService';
import type { JobProgressMessage } from './services/websocketService'; // type-only import
import type { Job } from './types'; // type-only import
import { JobStatus } from './types'; // Value import for enum-like object

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || '/api';
const WEBSOCKET_URL_PREFIX = import.meta.env.VITE_WEBSOCKET_URL_PREFIX || ''; // e.g., /api for Nginx proxy

// Helper to construct WebSocket URL correctly based on current window location and prefix
const getWebSocketURL = (job_id: number) => {
    const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
    const host = window.location.host;
    // If WEBSOCKET_URL_PREFIX is set (e.g. for proxy), it's used. Otherwise, direct connection.
    // For development, if backend is on 8000 and frontend on 5173, this needs to be adjusted.
    // Assuming backend is served on the same host or proxied.
    const baseWsUrl = WEBSOCKET_URL_PREFIX ? `${protocol}//${host}${WEBSOCKET_URL_PREFIX}` : `${protocol}//${host}`;
    // If running Vite dev server (e.g., port 5173) and backend is on 8000,
    // you might need to manually set the backend host for WebSocket in .env.development
    // For example, VITE_WEBSOCKET_URL_OVERRIDE=ws://localhost:8000
    const wsUrlOverride = import.meta.env.VITE_WEBSOCKET_URL_OVERRIDE;
    if (wsUrlOverride) {
        return `${wsUrlOverride}/ws/job_status/${job_id}`;
    }
    return `${baseWsUrl}/ws/job_status/${job_id}`;
};


// Simple component for displaying transcription
const TranscriptionViewer: React.FC<{ job: Job; onClose: () => void }> = ({ job, onClose }) => {
    const [textContent, setTextContent] = useState<string | null>(null);
    const [isLoading, setIsLoading] = useState(false);
    const [error, setError] = useState<string | null>(null);

    const getFileUrl = (filePath?: string) => {
        if (!filePath) return '#';
        // Assuming files are served relative to the domain root by Nginx or backend static serving
        return `${API_BASE_URL}/${filePath.startsWith('/') ? filePath.substring(1) : filePath}`;
    };

    useEffect(() => {
        if (job.status === JobStatus.COMPLETED && job.result_txt_path) {
            setIsLoading(true);
            setError(null);
            axios.get(getFileUrl(job.result_txt_path))
                .then(response => {
                    setTextContent(response.data);
                    setIsLoading(false);
                })
                .catch(err => {
                    console.error("Error fetching transcription text:", err);
                    setError("Failed to load transcription text.");
                    setIsLoading(false);
                });
        }
    }, [job.result_txt_path, job.status]);

    if (job.status !== JobStatus.COMPLETED || !job.result_txt_path) {
        return (
            <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center p-4 z-50">
                <div className="bg-white p-6 rounded-lg shadow-xl max-w-lg w-full">
                    <h3 className="text-lg font-semibold mb-2">Transcription Viewer</h3>
                    <p>Transcription is not available or the job is not complete.</p>
                    <button onClick={onClose} className="mt-4 px-4 py-2 bg-gray-300 rounded hover:bg-gray-400">Close</button>
                </div>
            </div>
        );
    }

    return (
        <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center p-4 z-50">
            <div className="bg-white p-6 rounded-lg shadow-xl max-w-2xl w-full h-3/4 flex flex-col">
                <div className="flex justify-between items-center mb-4">
                    <h3 className="text-xl font-semibold text-gray-800">Transcription: {job.filename}</h3>
                    <button onClick={onClose} className="text-2xl font-bold text-gray-500 hover:text-gray-700 transition-colors">&times;</button>
                </div>
                {isLoading && <p className="text-gray-600">Loading transcription...</p>}
                {error && <p className="text-red-500">{error}</p>}
                {textContent !== null && (
                    <textarea
                        readOnly
                        value={textContent}
                        className="w-full flex-grow p-3 border border-gray-300 rounded-md resize-none bg-gray-50 text-sm font-mono focus:ring-2 focus:ring-blue-500 focus:border-blue-500"
                        placeholder="Transcription text..."
                    />
                )}
                {!isLoading && textContent === null && !error && <p className="text-gray-500">No text content found or loaded.</p>}
            </div>
        </div>
    );
};


function App() {
    const [selectedFile, setSelectedFile] = useState<File | null>(null);
    const [uploading, setUploading] = useState(false);
    const [uploadProgress, setUploadProgress] = useState(0);
    const [currentProcessingJob, setCurrentProcessingJob] = useState<Job | null>(null);
    const [jobs, setJobs] = useState<Job[]>([]);
    const [appError, setAppError] = useState<string | null>(null);
    const [viewingTranscriptionForJob, setViewingTranscriptionForJob] = useState<Job | null>(null);

    const fileInputRef = useRef<HTMLInputElement>(null);


    const fetchJobs = useCallback(async () => {
        try {
            setAppError(null);
            const response = await axios.get<Job[]>(`${API_BASE_URL}/jobs/`);
            const sortedJobs = response.data.sort((a, b) =>
                new Date(b.created_at).getTime() - new Date(a.created_at).getTime()
            );
            setJobs(sortedJobs.map(job => ({...job, current_message: job.status}))); // Initialize current_message
        } catch (err) {
            console.error('Error fetching jobs:', err);
            setAppError('Failed to fetch job list. Backend might be unavailable.');
        }
    }, []);

    useEffect(() => {
        fetchJobs();
    }, [fetchJobs]);

    const handleFileChange = (event: React.ChangeEvent<HTMLInputElement>) => {
        if (event.target.files && event.target.files[0]) {
            setSelectedFile(event.target.files[0]);
            // Don't reset currentProcessingJob here, allow it to continue displaying
            setAppError(null);
        }
    };

    const handleUpload = async () => {
        if (!selectedFile) return;

        setUploading(true);
        setUploadProgress(0);
        // setCurrentProcessingJob(null); // Keep previous job visible until new one starts
        setAppError(null);

        const formData = new FormData();
        formData.append('file', selectedFile);

        try {
            const response = await axios.post<Job>(`${API_BASE_URL}/jobs/`, formData, {
                headers: { 'Content-Type': 'multipart/form-data' },
                onUploadProgress: (progressEvent) => {
                    const total = progressEvent.total || selectedFile.size;
                    if (total) { // Ensure total is not undefined or zero
                        const percentCompleted = Math.round((progressEvent.loaded * 100) / total);
                        setUploadProgress(percentCompleted);
                    }
                },
            });

            const newJob = response.data;
            console.log('Upload successful, job created:', newJob);
            setUploading(false);

            // Add to list and set as current processing job
            const jobWithUiState = { ...newJob, progress: 0, current_message: 'Connecting to status updates...' };
            setJobs(prevJobs => [jobWithUiState, ...prevJobs].sort((a, b) => new Date(b.created_at).getTime() - new Date(a.created_at).getTime()));
            setCurrentProcessingJob(jobWithUiState);

            setSelectedFile(null);
            if(fileInputRef.current) fileInputRef.current.value = "";


            websocketService.connect(
                newJob.id,
                // getWebSocketURL(newJob.id), // This was the extra argument, URL is constructed internally by the service
                (data: JobProgressMessage) => {
                    console.log('Job update received via WebSocket:', data);
                    setAppError(null);

                    const updateJobState = (prev: Job | null): Job | null => {
                        if (!prev || prev.id !== newJob.id) return prev; // Ensure we're updating the correct job
                        return {
                            ...prev,
                            status: data.status,
                            progress: data.progress !== undefined ? data.progress : (data.status === JobStatus.COMPLETED ? 100 : prev.progress),
                            current_message: data.message || data.status.toString(),
                            result_txt_path: data.txt_path || prev.result_txt_path,
                            result_srt_path: data.srt_path || prev.result_srt_path,
                            duration_seconds: data.duration !== undefined ? data.duration : prev.duration_seconds,
                            error_message: data.error || (data.status === JobStatus.FAILED ? data.message : prev.error_message),
                            updated_at: new Date().toISOString(),
                        };
                    };

                    setCurrentProcessingJob(updateJobState);
                    setJobs(prevJobsList => prevJobsList.map(job => job.id === newJob.id ? updateJobState(job) as Job : job));
                },
                (errorEvent) => {
                    console.error('WebSocket error for job', newJob.id, errorEvent);
                    const errorMsg = 'WebSocket connection error. Status updates may be delayed or unavailable.';
                    setCurrentProcessingJob(prev => prev && prev.id === newJob.id ? { ...prev, current_message: errorMsg, status: prev.status === JobStatus.PENDING || prev.status === JobStatus.PROCESSING ? JobStatus.FAILED : prev.status, error_message: prev.error_message || errorMsg } : prev);
                    setAppError(`WebSocket connection error for Job ID ${newJob.id}.`);
                },
                (closeEvent) => {
                    console.log('WebSocket closed for job', newJob.id, `Code: ${closeEvent.code}, Reason: ${closeEvent.reason}, WasClean: ${closeEvent.wasClean}`);
                    setCurrentProcessingJob(prev => {
                        if (prev && prev.id === newJob.id && prev.status !== JobStatus.COMPLETED && prev.status !== JobStatus.FAILED) {
                            const message = `Status updates disconnected (Code: ${closeEvent.code}). Refresh to see final status.`;
                            setAppError(message); // Show a general error if WS disconnects unexpectedly
                            return { ...prev, current_message: message };
                        }
                        return prev;
                    });
                }
            );

        } catch (err) {
            console.error('Error uploading file:', err);
            setUploading(false);
            const axiosError = err as AxiosError;
            let errorMessage = 'An unknown error occurred during upload.';
            if (axiosError.response) {
                errorMessage = `Upload failed: ${(axiosError.response.data as any)?.detail || axiosError.message}`;
            } else if (axiosError.request) {
                errorMessage = 'Upload failed: No response from server. Is the backend running?';
            } else {
                errorMessage = `Upload failed: ${axiosError.message}`;
            }
            setAppError(errorMessage); // Use appError for upload errors
            // Optionally create a temporary job display for the failed upload
            // For simplicity, we'll rely on the error message display for now.
        }
    };

    useEffect(() => {
        return () => {
            // This will be called when the component unmounts.
            // websocketService.close() will close any active connection.
            console.log("App component unmounting, closing WebSocket.");
            websocketService.close();
        };
    }, []); // Empty dependency array ensures this runs only on mount and unmount

    const getDownloadUrl = (filePath?: string) => {
        if (!filePath) return '#';
        // Assuming files are served relative to the domain root.
        // For local dev, this might be http://localhost:8000/transcription_results/...
        // For production, Nginx would handle serving from /transcription_results/
        const backendHost = import.meta.env.VITE_API_URL || ''; // e.g., http://localhost:8000
        return `${backendHost}/${filePath.startsWith('/') ? filePath.substring(1) : filePath}`;
    };

    const handleViewTranscription = (job: Job) => {
        if (job.status === JobStatus.COMPLETED && job.result_txt_path) {
            setViewingTranscriptionForJob(job);
        } else {
            alert("Transcription is not available or the job is not complete.");
        }
    };

    const getStatusColor = (status: JobStatus) => {
        switch (status) {
            case JobStatus.COMPLETED: return 'text-green-600';
            case JobStatus.PROCESSING: return 'text-blue-600';
            case JobStatus.PENDING: return 'text-orange-500';
            case JobStatus.FAILED: return 'text-red-600';
            default: return 'text-gray-600';
        }
    };

    const getStatusBorderColor = (status: JobStatus) => {
        switch (status) {
            case JobStatus.COMPLETED: return 'border-green-500';
            case JobStatus.PROCESSING: return 'border-blue-500';
            case JobStatus.PENDING: return 'border-yellow-500';
            case JobStatus.FAILED: return 'border-red-500';
            default: return 'border-gray-300';
        }
    };

    return (
        <div className="min-h-screen bg-gradient-to-br from-slate-900 to-slate-800 text-gray-200 font-sans">
            <header className="bg-slate-800/50 backdrop-blur-md shadow-lg sticky top-0 z-40">
                <div className="container mx-auto p-4 flex justify-between items-center">
                    <h1 className="text-3xl font-bold text-transparent bg-clip-text bg-gradient-to-r from-purple-400 to-pink-600">Audio Transcription Service</h1>
                </div>
            </header>

            <main className="container mx-auto p-4 sm:p-6 md:p-8">
                {appError && (
                    <div className="mb-6 p-4 bg-red-700/20 border border-red-500 text-red-300 rounded-lg shadow-md" role="alert">
                        <div className="flex items-center">
                            <svg xmlns="http://www.w3.org/2000/svg" className="h-6 w-6 mr-2 text-red-400" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M12 8v4m0 4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
                            </svg>
                            <div>
                                <p className="font-semibold">Error</p>
                                <p>{appError}</p>
                            </div>
                        </div>
                    </div>
                )}

                <section className="mb-8 p-6 bg-slate-700/50 backdrop-blur-sm border border-slate-600 rounded-xl shadow-xl">
                    <h2 className="text-2xl font-semibold mb-4 text-slate-100">Upload New Audio File</h2>
                    <div className="flex flex-col sm:flex-row items-center space-y-3 sm:space-y-0 sm:space-x-4">
                        <label htmlFor="file-upload" className="flex-grow w-full sm:w-auto">
                            <span className="sr-only">Choose file</span>
                            <input
                                id="file-upload"
                                type="file"
                                accept=".mp3,.wav,.m4a,.ogg,.flac,.aac"
                                onChange={handleFileChange}
                                ref={fileInputRef}
                                className="block w-full text-sm text-slate-400 file:cursor-pointer
                                           file:mr-4 file:py-2 file:px-4
                                           file:rounded-lg file:border-0
                                           file:text-sm file:font-semibold
                                           file:bg-violet-600 file:text-violet-50
                                           hover:file:bg-violet-700"
                            />
                        </label>
                         {selectedFile && <p className="text-sm text-slate-300 flex-shrink-0 pt-2 sm:pt-0">Selected: {selectedFile.name}</p>}
                    </div>

                    <button
                        onClick={handleUpload}
                        disabled={!selectedFile || uploading}
                        className="mt-4 w-full sm:w-auto px-6 py-3 bg-gradient-to-r from-purple-600 to-pink-600 text-white font-semibold rounded-lg shadow-md hover:from-purple-700 hover:to-pink-700 disabled:opacity-50 disabled:cursor-not-allowed transition duration-150 ease-in-out focus:outline-none focus:ring-2 focus:ring-pink-500 focus:ring-opacity-50"
                    >
                        {uploading ? `Uploading (${uploadProgress}%)` : 'Upload and Transcribe'}
                    </button>
                    {uploading && (
                        <div className="w-full bg-slate-600 rounded-full h-2.5 mt-4 overflow-hidden">
                            <div className="bg-green-500 h-2.5 rounded-full transition-all duration-300 ease-linear" style={{ width: `${uploadProgress}%` }}></div>
                        </div>
                    )}
                </section>

                {currentProcessingJob && (
                    <section className={`mb-8 p-6 border rounded-xl shadow-xl bg-slate-700/50 backdrop-blur-sm ${getStatusBorderColor(currentProcessingJob.status)} border-l-4 transition-all duration-500 ease-in-out`}>
                        <h3 className="text-xl font-semibold mb-3 text-slate-100">
                            Current Job: <span className="font-normal italic">{currentProcessingJob.filename}</span> (ID: {currentProcessingJob.id})
                        </h3>
                        <p className="text-sm">Status: <span className={`font-bold ${getStatusColor(currentProcessingJob.status)}`}>{currentProcessingJob.status.toUpperCase()}</span></p>

                        {currentProcessingJob.status === JobStatus.PROCESSING && currentProcessingJob.progress !== undefined && (
                            <div className="mt-2">
                                <p className="text-xs text-slate-400 mb-1">{currentProcessingJob.current_message || 'Processing...'}</p>
                                <div className="w-full bg-slate-600 rounded-full h-4 overflow-hidden">
                                    <div
                                        className="bg-gradient-to-r from-blue-500 to-purple-600 h-4 rounded-full flex items-center justify-center text-xs text-white font-medium transition-all duration-300 ease-linear"
                                        style={{ width: `${currentProcessingJob.progress}%` }}
                                    >
                                        {currentProcessingJob.progress}%
                                    </div>
                                </div>
                            </div>
                        )}
                        {currentProcessingJob.status !== JobStatus.PROCESSING && currentProcessingJob.current_message && (
                            <p className="text-sm text-slate-300 mt-1">Details: {currentProcessingJob.current_message}</p>
                        )}

                        {currentProcessingJob.status === JobStatus.COMPLETED && (
                            <div className="mt-3 space-x-2">
                                <p className="text-sm mb-1">Duration: {currentProcessingJob.duration_seconds?.toFixed(2)}s</p>
                                <button onClick={() => handleViewTranscription(currentProcessingJob)} className="px-3 py-1 bg-green-600 text-white text-sm rounded-md hover:bg-green-700 transition">View Text</button>
                                {currentProcessingJob.result_srt_path && (
                                    <a href={getDownloadUrl(currentProcessingJob.result_srt_path)} download className="px-3 py-1 bg-indigo-500 text-white text-sm rounded-md hover:bg-indigo-600 transition">Download .srt</a>
                                )}
                                {currentProcessingJob.result_txt_path && ( // Ensure this is also available if view text is shown
                                    <a href={getDownloadUrl(currentProcessingJob.result_txt_path)} download className="px-3 py-1 bg-purple-500 text-white text-sm rounded-md hover:bg-purple-600 transition">Download .txt</a>
                                )}
                            </div>
                        )}
                        {currentProcessingJob.status === JobStatus.FAILED && currentProcessingJob.error_message && (
                             <p className="text-sm text-red-400 mt-1">Error: {currentProcessingJob.error_message}</p>
                        )}
                         <p className="text-xs text-slate-400 mt-2">Last updated: {new Date(currentProcessingJob.updated_at).toLocaleString()}</p>
                    </section>
                )}

                <section className="p-6 bg-slate-700/50 backdrop-blur-sm border border-slate-600 rounded-xl shadow-xl">
                    <div className="flex justify-between items-center mb-4">
                        <h2 className="text-2xl font-semibold text-slate-100">Transcription History</h2>
                        <button
                            onClick={fetchJobs}
                            disabled={uploading}
                            className="px-4 py-2 text-sm bg-slate-600 text-slate-200 rounded-lg hover:bg-slate-500 transition focus:outline-none focus:ring-2 focus:ring-slate-400"
                        >
                            Refresh List
                        </button>
                    </div>
                    {jobs.length === 0 && !appError ? <p className="text-slate-400">No transcription jobs found. Upload a file to get started!</p> : null}
                    <div className="space-y-4">
                        {jobs.map(job => (
                            <article key={job.id} className={`p-4 border ${getStatusBorderColor(job.status)} rounded-lg shadow-md hover:shadow-lg transition-shadow duration-300 ease-in-out ${job.id === currentProcessingJob?.id ? 'bg-slate-600/70' : 'bg-slate-700/30'}`}>
                                <div className="flex flex-col sm:flex-row justify-between sm:items-start mb-1">
                                    <h4 className="font-semibold text-lg text-slate-100 truncate" title={job.filename}>{job.filename}</h4>
                                    <p className="text-xs text-slate-400 sm:ml-2 flex-shrink-0">ID: {job.id}</p>
                                </div>
                                <p className="text-sm mb-1">Status: <span className={`font-semibold ${getStatusColor(job.status)}`}>{job.status.toUpperCase()}</span></p>

                                {job.status === JobStatus.PROCESSING && job.id === currentProcessingJob?.id && job.progress !== undefined && (
                                     <div className="w-full bg-slate-600 rounded-full h-2.5 my-1">
                                        <div className="bg-blue-500 h-2.5 rounded-full transition-width duration-300" style={{ width: `${job.progress}%` }}></div>
                                    </div>
                                )}
                                {job.current_message && job.id === currentProcessingJob?.id && <p className="text-xs text-slate-300 truncate" title={job.current_message}>Update: {job.current_message}</p>}

                                <p className="text-xs text-slate-400">Created: {new Date(job.created_at).toLocaleString()}</p>
                                <p className="text-xs text-slate-400">Last Updated: {new Date(job.updated_at).toLocaleString()}</p>

                                {job.status === JobStatus.COMPLETED && (
                                    <div className="mt-2 space-x-2">
                                        <button onClick={() => handleViewTranscription(job)} className="px-3 py-1 bg-green-600 text-white text-xs rounded-md hover:bg-green-700 transition">View Text</button>
                                        {job.result_srt_path && <a href={getDownloadUrl(job.result_srt_path)} download className="px-3 py-1 bg-indigo-500 text-white text-xs rounded-md hover:bg-indigo-600 transition">Download .srt</a>}
                                        {job.result_txt_path && <a href={getDownloadUrl(job.result_txt_path)} download className="px-3 py-1 bg-purple-500 text-white text-xs rounded-md hover:bg-purple-600 transition">Download .txt</a>}
                                    </div>
                                )}
                                 {job.status === JobStatus.FAILED && job.error_message && (
                                    <p className="text-xs text-red-400 mt-1 truncate" title={job.error_message}>Error: {job.error_message}</p>
                                )}
                            </article>
                        ))}
                    </div>
                </section>
            </main>
            {viewingTranscriptionForJob && (
                <TranscriptionViewer
                    job={viewingTranscriptionForJob}
                    onClose={() => setViewingTranscriptionForJob(null)}
                />
            )}
             <footer className="text-center py-8 mt-12 text-sm text-slate-400 border-t border-slate-700">
                <p>&copy; {new Date().getFullYear()} Audio Transcription Service. Powered by AI.</p>
            </footer>
        </div>
    );
}

export default App;
