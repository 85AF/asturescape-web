// frontend/src/services/websocketService.ts
import { JobStatus } from '../types'; // Assuming a types file exists or will be created

export interface JobProgressMessage {
    status: JobStatus;
    message?: string;
    progress?: number; // Percentage e.g., 0-100
    txt_path?: string;
    srt_path?: string;
    duration?: number; // This was 'duration_seconds' in Job model, ensure consistency or map
    error?: string; // Error message if status is FAILED
}

const MAX_RECONNECT_ATTEMPTS = 5;
const RECONNECT_DELAY_MS = 3000;

class WebSocketService {
    private socket: WebSocket | null = null;
    private onMessageCallback: ((data: JobProgressMessage) => void) | null = null;
    private onErrorCallback: ((event: Event) => void) | null = null;
    private onCloseCallback: ((event: CloseEvent) => void) | null = null;
    private job_id: number | null = null;
    private reconnectAttempts: number = 0;
    private explicitlyClosed: boolean = false;

    public connect(
        job_id: number,
        onMessage: (data: JobProgressMessage) => void,
        onError?: (event: Event) => void,
        onClose?: (event: CloseEvent) => void
    ): void {
        if (this.socket && this.socket.readyState === WebSocket.OPEN) {
            if (this.job_id === job_id) {
                console.log('WebSocket already connected to job_id:', job_id);
                // Update callbacks if they've changed
                this.onMessageCallback = onMessage;
                this.onErrorCallback = onError || null;
                this.onCloseCallback = onClose || null;
                return;
            }
            // If connecting to a new job, close the old one first
            console.log(`WebSocket closing for job_id ${this.job_id} to connect to new job_id ${job_id}`);
            this.close(true); // Close existing connection before opening a new one
        }

        this.job_id = job_id;
        this.explicitlyClosed = false; // Reset explicit close flag
        const wsProtocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
        const wsUrl = `${wsProtocol}//${window.location.host}/ws/job_status/${job_id}`;

        console.log(`Connecting to WebSocket: ${wsUrl}`);
        this.socket = new WebSocket(wsUrl);
        this.onMessageCallback = onMessage;
        this.onErrorCallback = onError || null;
        this.onCloseCallback = onClose || null;
        this.reconnectAttempts = 0;

        this.socket.onopen = () => {
            console.log(`WebSocket connected for job_id: ${job_id}`);
            this.reconnectAttempts = 0; // Reset on successful connection
        };

        this.socket.onmessage = (event) => {
            try {
                const data = JSON.parse(event.data as string) as JobProgressMessage;
                console.log('WebSocket message received:', data);
                if (this.onMessageCallback) {
                    this.onMessageCallback(data);
                }
            } catch (error) {
                console.error('Error parsing WebSocket message or in callback:', error);
            }
        };

        this.socket.onerror = (event) => {
            console.error('WebSocket error:', event);
            if (this.onErrorCallback) {
                this.onErrorCallback(event);
            }
            // Reconnection logic is typically handled in onclose
        };

        this.socket.onclose = (event) => {
            console.log(`WebSocket closed for job_id: ${this.job_id}. Code: ${event.code}, Reason: ${event.reason}, Clean: ${event.wasClean}`);
            if (this.onCloseCallback) {
                this.onCloseCallback(event);
            }

            // Attempt to reconnect if not explicitly closed and not a normal closure (1000)
            if (!this.explicitlyClosed && event.code !== 1000 && this.reconnectAttempts < MAX_RECONNECT_ATTEMPTS) {
                this.reconnectAttempts++;
                console.log(`Attempting to reconnect (${this.reconnectAttempts}/${MAX_RECONNECT_ATTEMPTS}) for job_id: ${this.job_id}...`);
                setTimeout(() => {
                    // Ensure we are still supposed to be connected to this job_id
                    if (this.job_id === job_id && !this.explicitlyClosed) {
                        this.connect(job_id, this.onMessageCallback!, this.onErrorCallback ?? undefined, this.onCloseCallback ?? undefined);
                    }
                }, RECONNECT_DELAY_MS * Math.pow(2, this.reconnectAttempts -1)); // Exponential backoff
            } else if (this.reconnectAttempts >= MAX_RECONNECT_ATTEMPTS) {
                console.error("Max WebSocket reconnect attempts reached for job_id:", this.job_id);
            }
            // If explicitly closed, this.socket will be null, preventing reconnection.
        };
    }

    public sendMessage(message: string | object): void {
        if (this.socket && this.socket.readyState === WebSocket.OPEN) {
            const msgToSend = typeof message === 'string' ? message : JSON.stringify(message);
            this.socket.send(msgToSend);
            console.log('WebSocket message sent:', msgToSend);
        } else {
            console.error('WebSocket is not connected. Cannot send message.');
        }
    }

    public close(isInternalClose: boolean = false): void {
        if (this.socket) {
            if (!isInternalClose) { // Only set explicitlyClosed if called externally
                this.explicitlyClosed = true;
            }
            console.log(`Closing WebSocket for job_id: ${this.job_id}. Explicitly closed: ${this.explicitlyClosed}`);
            this.socket.close(1000, "Client initiated disconnect");
            this.socket = null; // Important to prevent reconnection attempts by onclose if this was an explicit close
            // Do not nullify job_id here if we are about to reconnect to a new one immediately.
            // It will be set by the new connect() call.
            // If this is a final close (e.g. component unmount), job_id can be nulled.
             if (this.explicitlyClosed) { // Full cleanup if it's a definitive close
                this.job_id = null;
                this.onMessageCallback = null;
                this.onErrorCallback = null;
                this.onCloseCallback = null;
            }
        }
    }
}

export const websocketService = new WebSocketService();
