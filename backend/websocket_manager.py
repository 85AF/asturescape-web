# backend/websocket_manager.py
import logging
from fastapi import WebSocket
from typing import Dict, List

logger = logging.getLogger(__name__)

class ConnectionManager:
    def __init__(self):
        # Store connections per job_id
        self.active_connections: Dict[int, List[WebSocket]] = {}

    async def connect(self, websocket: WebSocket, job_id: int):
        await websocket.accept()
        if job_id not in self.active_connections:
            self.active_connections[job_id] = []
        self.active_connections[job_id].append(websocket)
        logger.info(f"WebSocket connected: {websocket.client} for job_id: {job_id}")
        logger.info(f"Active connections for job {job_id}: {len(self.active_connections[job_id])}")


    def disconnect(self, websocket: WebSocket, job_id: int):
        if job_id in self.active_connections:
            if websocket in self.active_connections[job_id]:
                self.active_connections[job_id].remove(websocket)
                if not self.active_connections[job_id]: # If no more connections for this job_id
                    del self.active_connections[job_id]
                logger.info(f"WebSocket disconnected: {websocket.client} for job_id: {job_id}")
            else:
                logger.warning(f"Websocket {websocket.client} not found for job_id {job_id} during disconnect.")
        else:
            logger.warning(f"Job_id {job_id} not found in active_connections during disconnect.")


    async def send_job_update(self, job_id: int, message: dict):
        if job_id in self.active_connections:
            disconnected_sockets = []
            # Make a copy of the list for iteration, as disconnect can modify the original list
            connections_to_notify = list(self.active_connections[job_id])

            for connection in connections_to_notify:
                try:
                    await connection.send_json(message)
                    logger.info(f"Sent message to {connection.client} for job {job_id}: {message}")
                except Exception as e: # Could be WebSocketDisconnect or other errors
                    logger.error(f"Error sending message to {connection.client} for job {job_id}: {e}. Marking for disconnect.")
                    # Mark for disconnection, but don't modify list while iterating
                    disconnected_sockets.append(connection)

            # Clean up disconnected sockets after iteration
            for ws in disconnected_sockets:
                # Check if ws is still in the original list before attempting to disconnect.
                # This handles cases where a socket might have been removed by another process/task
                # or if disconnect was called multiple times for the same socket.
                if job_id in self.active_connections and ws in self.active_connections[job_id]:
                    self.disconnect(ws, job_id)
        else:
            logger.info(f"No active WebSocket connections for job_id: {job_id} to send update: {message}")

# Global instance of ConnectionManager
manager = ConnectionManager()
