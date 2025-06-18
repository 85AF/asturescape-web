// frontend/src/types.ts
export const JobStatus = {
    PENDING: "pending",
    PROCESSING: "processing",
    COMPLETED: "completed",
    FAILED: "failed",
} as const;

export type JobStatus = typeof JobStatus[keyof typeof JobStatus];

export interface Job {
    id: number;
    filename: string;
    status: JobStatus;
    created_at: string; // ISO date string
    updated_at: string; // ISO date string
    duration_seconds?: number;
    result_txt_path?: string;
    result_srt_path?: string;
    error_message?: string;
    // For frontend state tracking
    progress?: number; // e.g. 0-100, derived from WebSocket messages
    current_message?: string; // Last message from WebSocket
}
