from typing import Dict, List, Any
from fastapi import WebSocket
import json

class ConnectionManager:
    def __init__(self):
        self.active_connections: Dict[str, List[WebSocket]] = {}

    async def connect(self, job_id: str, websocket: WebSocket):
        await websocket.accept()
        if job_id not in self.active_connections:
            self.active_connections[job_id] = []
        self.active_connections[job_id].append(websocket)

    def disconnect(self, job_id: str, websocket: WebSocket):
        if job_id in self.active_connections:
            if websocket in self.active_connections[job_id]:
                self.active_connections[job_id].remove(websocket)
            if not self.active_connections[job_id]:
                del self.active_connections[job_id]

    async def broadcast(self, job_id: str, message: Dict[str, Any]):
        if job_id in self.active_connections:
            # Copy list to avoid modification during iteration
            for connection in list(self.active_connections[job_id]):
                try:
                    await connection.send_json(message)
                except Exception:
                    # Handle disconnected clients gracefully
                    self.disconnect(job_id, connection)

manager = ConnectionManager()
