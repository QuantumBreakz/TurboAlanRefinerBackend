from __future__ import annotations

from typing import Dict, List
import asyncio
import time
import logging

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

logger = logging.getLogger(__name__)

router = APIRouter()


class ConnectionManager:
    def __init__(self) -> None:
        self.active_connections: Dict[str, List[WebSocket]] = {}

    async def connect(self, websocket: WebSocket, job_id: str) -> None:
        await websocket.accept()
        self.active_connections.setdefault(job_id, []).append(websocket)
        logger.info(f"WebSocket connected for job {job_id} (total connections: {len(self.active_connections.get(job_id, []))})")

    def disconnect(self, websocket: WebSocket, job_id: str) -> None:
        conns = self.active_connections.get(job_id)
        if not conns:
            return
        if websocket in conns:
            conns.remove(websocket)
            logger.info(f"WebSocket disconnected for job {job_id} (remaining connections: {len(conns)})")
        if not conns:
            self.active_connections.pop(job_id, None)

    async def broadcast(self, job_id: str, data: dict) -> None:
        conns = self.active_connections.get(job_id, [])
        if not conns:
            logger.debug(f"No WebSocket connections for job {job_id} to broadcast to")
            return
        to_remove: List[WebSocket] = []
        for ws in conns:
            try:
                await ws.send_json(data)
            except Exception as e:
                logger.warning(f"Failed to send WebSocket message to job {job_id}: {e}")
                to_remove.append(ws)
        for ws in to_remove:
            self.disconnect(ws, job_id)


manager = ConnectionManager()


@router.websocket("/ws/progress/{job_id}")
async def websocket_progress(websocket: WebSocket, job_id: str):
    """WebSocket endpoint for real-time job progress updates.
    
    Clients connect to receive real-time updates for a specific job.
    The connection stays open until the client disconnects or the job completes.
    """
    logger.info(f"WebSocket connection attempt for job {job_id}")
    try:
        await manager.connect(websocket, job_id)
        
        # Send initial connection confirmation
        await websocket.send_json({
            "type": "connected",
            "jobId": job_id,
            "message": "WebSocket connected successfully"
        })
        
        # Heartbeat loop to keep connection alive and detect disconnects
        while True:
            try:
                # Wait for either a message from client or timeout
                # This allows us to detect disconnects quickly
                try:
                    # Try to receive a message (with timeout)
                    await asyncio.wait_for(websocket.receive_text(), timeout=5.0)
                except asyncio.TimeoutError:
                    # Timeout is expected - send heartbeat
                    pass
                except WebSocketDisconnect:
                    # Client disconnected normally
                    break
                
                # Send heartbeat
                await websocket.send_json({
                    "type": "heartbeat",
                    "jobId": job_id,
                    "ts": time.time(),
                })
            except WebSocketDisconnect:
                # Client disconnected
                break
            except Exception as e:
                logger.error(f"WebSocket error for job {job_id}: {e}")
                break
    except Exception as e:
        logger.error(f"WebSocket connection error for job {job_id}: {e}")
    finally:
        manager.disconnect(websocket, job_id)
        logger.info(f"WebSocket connection closed for job {job_id}")









