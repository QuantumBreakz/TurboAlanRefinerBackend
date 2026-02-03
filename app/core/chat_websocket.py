"""
Real-time Chat WebSocket Manager
Handles WebSocket connections for collaborative chat features including:
- Message broadcasting
- Typing indicators
- Presence (online/offline status)
- Document context updates
"""
from typing import Dict, List, Set, Any, Optional
from fastapi import WebSocket, WebSocketDisconnect
from dataclasses import dataclass, field
import json
import asyncio
import time
import logging

logger = logging.getLogger(__name__)


@dataclass
class UserPresence:
    """Tracks a user's presence in a workspace"""
    user_id: str
    workspace_id: str
    websocket: WebSocket
    connected_at: float = field(default_factory=time.time)
    last_activity: float = field(default_factory=time.time)
    is_typing: bool = False
    typing_started_at: Optional[float] = None


class ChatWebSocketManager:
    """
    Manages WebSocket connections for real-time chat collaboration.
    
    Features:
    - Per-workspace connection management
    - Message broadcasting to all participants
    - Typing indicators
    - Presence tracking (who's online)
    """
    
    def __init__(self):
        # workspace_id -> list of UserPresence
        self.connections: Dict[str, List[UserPresence]] = {}
        # user_id -> list of workspace_ids they're connected to
        self.user_connections: Dict[str, Set[str]] = {}
        # Lock for thread-safe operations
        self._lock = asyncio.Lock()
        # Typing indicator timeout (seconds)
        self.typing_timeout = 5.0
    
    async def connect(
        self,
        workspace_id: str,
        user_id: str,
        websocket: WebSocket
    ) -> UserPresence:
        """Accept a WebSocket connection and register user presence"""
        await websocket.accept()
        
        async with self._lock:
            # Create presence record
            presence = UserPresence(
                user_id=user_id,
                workspace_id=workspace_id,
                websocket=websocket
            )
            
            # Add to workspace connections
            if workspace_id not in self.connections:
                self.connections[workspace_id] = []
            self.connections[workspace_id].append(presence)
            
            # Track user's connections
            if user_id not in self.user_connections:
                self.user_connections[user_id] = set()
            self.user_connections[user_id].add(workspace_id)
        
        # Broadcast user joined
        await self.broadcast_presence_update(workspace_id, user_id, "joined")
        
        return presence
    
    async def disconnect(
        self,
        workspace_id: str,
        user_id: str,
        websocket: WebSocket
    ):
        """Remove a user's WebSocket connection"""
        async with self._lock:
            if workspace_id in self.connections:
                # Find and remove the specific connection
                self.connections[workspace_id] = [
                    p for p in self.connections[workspace_id]
                    if not (p.user_id == user_id and p.websocket == websocket)
                ]
                
                # Clean up empty workspace
                if not self.connections[workspace_id]:
                    del self.connections[workspace_id]
            
            # Update user connections tracking
            if user_id in self.user_connections:
                # Check if user still has other connections to this workspace
                still_connected = any(
                    p.user_id == user_id
                    for p in self.connections.get(workspace_id, [])
                )
                if not still_connected:
                    self.user_connections[user_id].discard(workspace_id)
                    if not self.user_connections[user_id]:
                        del self.user_connections[user_id]
        
        # Broadcast user left
        await self.broadcast_presence_update(workspace_id, user_id, "left")
    
    async def broadcast_message(
        self,
        workspace_id: str,
        message: Dict[str, Any],
        exclude_user: Optional[str] = None
    ):
        """Broadcast a message to all users in a workspace"""
        if workspace_id not in self.connections:
            return
        
        payload = {
            "type": "message",
            "workspace_id": workspace_id,
            "data": message,
            "timestamp": time.time()
        }
        
        # Send to all connections (creating a copy to avoid modification during iteration)
        connections = list(self.connections.get(workspace_id, []))
        disconnected = []
        
        for presence in connections:
            if exclude_user and presence.user_id == exclude_user:
                continue
            try:
                await presence.websocket.send_json(payload)
            except Exception as e:
                logger.warning(f"WebSocket send failed for user {presence.user_id} in workspace {workspace_id}: {e}")
                disconnected.append(presence)
        
        # Clean up disconnected clients
        for presence in disconnected:
            await self.disconnect(workspace_id, presence.user_id, presence.websocket)
    
    async def broadcast_typing(
        self,
        workspace_id: str,
        user_id: str,
        is_typing: bool
    ):
        """Broadcast typing indicator"""
        if workspace_id not in self.connections:
            return
        
        # Update the user's typing status
        async with self._lock:
            for presence in self.connections.get(workspace_id, []):
                if presence.user_id == user_id:
                    presence.is_typing = is_typing
                    presence.typing_started_at = time.time() if is_typing else None
                    presence.last_activity = time.time()
                    break
        
        payload = {
            "type": "typing",
            "workspace_id": workspace_id,
            "data": {
                "user_id": user_id,
                "is_typing": is_typing
            },
            "timestamp": time.time()
        }
        
        # Send to all except the typing user
        connections = list(self.connections.get(workspace_id, []))
        disconnected = []
        
        for presence in connections:
            if presence.user_id == user_id:
                continue
            try:
                await presence.websocket.send_json(payload)
            except Exception as e:
                logger.warning(f"WebSocket send failed for user {presence.user_id} in workspace {workspace_id} (typing indicator): {e}")
                disconnected.append(presence)
        
        for presence in disconnected:
            await self.disconnect(workspace_id, presence.user_id, presence.websocket)
    
    async def broadcast_presence_update(
        self,
        workspace_id: str,
        user_id: str,
        status: str  # "joined" | "left" | "active"
    ):
        """Broadcast presence update (user joined/left)"""
        if workspace_id not in self.connections:
            return
        
        # Get current online users
        online_users = self.get_online_users(workspace_id)
        
        payload = {
            "type": "presence",
            "workspace_id": workspace_id,
            "data": {
                "user_id": user_id,
                "status": status,
                "online_users": online_users
            },
            "timestamp": time.time()
        }
        
        connections = list(self.connections.get(workspace_id, []))
        disconnected = []
        
        for presence in connections:
            try:
                await presence.websocket.send_json(payload)
            except Exception as e:
                logger.warning(f"WebSocket send failed for user {presence.user_id} in workspace {workspace_id} (presence broadcast): {e}")
                disconnected.append(presence)
        
        for presence in disconnected:
            await self.disconnect(workspace_id, presence.user_id, presence.websocket)
    
    async def broadcast_document_update(
        self,
        workspace_id: str,
        document_id: str,
        update_type: str,  # "added" | "removed" | "active_changed" | "processing_update"
        data: Dict[str, Any]
    ):
        """Broadcast document context updates"""
        if workspace_id not in self.connections:
            return
        
        payload = {
            "type": "document_update",
            "workspace_id": workspace_id,
            "data": {
                "document_id": document_id,
                "update_type": update_type,
                **data
            },
            "timestamp": time.time()
        }
        
        connections = list(self.connections.get(workspace_id, []))
        disconnected = []
        
        for presence in connections:
            try:
                await presence.websocket.send_json(payload)
            except Exception as e:
                logger.warning(f"WebSocket send failed for user {presence.user_id} in workspace {workspace_id} (document update): {e}")
                disconnected.append(presence)
        
        for presence in disconnected:
            await self.disconnect(workspace_id, presence.user_id, presence.websocket)
    
    def get_online_users(self, workspace_id: str) -> List[str]:
        """Get list of unique user IDs currently connected to a workspace"""
        if workspace_id not in self.connections:
            return []
        
        # Get unique user IDs
        user_ids = set()
        for presence in self.connections[workspace_id]:
            user_ids.add(presence.user_id)
        
        return list(user_ids)
    
    def get_typing_users(self, workspace_id: str) -> List[str]:
        """Get list of users currently typing in a workspace"""
        if workspace_id not in self.connections:
            return []
        
        typing_users = []
        current_time = time.time()
        
        for presence in self.connections[workspace_id]:
            if presence.is_typing:
                # Check if typing hasn't timed out
                if presence.typing_started_at and (current_time - presence.typing_started_at) < self.typing_timeout:
                    typing_users.append(presence.user_id)
        
        return list(set(typing_users))
    
    def get_workspace_stats(self, workspace_id: str) -> Dict[str, Any]:
        """Get statistics for a workspace"""
        online_users = self.get_online_users(workspace_id)
        typing_users = self.get_typing_users(workspace_id)
        
        return {
            "workspace_id": workspace_id,
            "online_count": len(online_users),
            "online_users": online_users,
            "typing_users": typing_users,
            "connection_count": len(self.connections.get(workspace_id, []))
        }
    
    async def send_to_user(
        self,
        user_id: str,
        message: Dict[str, Any],
        workspace_id: Optional[str] = None
    ):
        """Send a message to a specific user (in all or specific workspace)"""
        target_workspaces = (
            [workspace_id] if workspace_id 
            else list(self.user_connections.get(user_id, set()))
        )
        
        payload = {
            "type": "direct",
            "data": message,
            "timestamp": time.time()
        }
        
        for ws_id in target_workspaces:
            connections = list(self.connections.get(ws_id, []))
            for presence in connections:
                if presence.user_id == user_id:
                    try:
                        await presence.websocket.send_json(payload)
                    except Exception as e:
                        logger.debug(f"WebSocket send failed for user {user_id} in workspace {ws_id} (direct message): {e}")
                        # User might have disconnected, continue silently
    
    async def handle_client_message(
        self,
        workspace_id: str,
        user_id: str,
        message: Dict[str, Any]
    ):
        """Handle incoming WebSocket message from a client"""
        msg_type = message.get("type", "")
        
        if msg_type == "typing":
            is_typing = message.get("data", {}).get("is_typing", False)
            await self.broadcast_typing(workspace_id, user_id, is_typing)
        
        elif msg_type == "ping":
            # Update last activity
            async with self._lock:
                for presence in self.connections.get(workspace_id, []):
                    if presence.user_id == user_id:
                        presence.last_activity = time.time()
                        break
            
            # Send pong
            await self.send_to_user(user_id, {"type": "pong"}, workspace_id)
        
        elif msg_type == "request_presence":
            # Send current presence info
            stats = self.get_workspace_stats(workspace_id)
            await self.send_to_user(user_id, {"type": "presence_info", **stats}, workspace_id)


# Global chat WebSocket manager instance
chat_ws_manager = ChatWebSocketManager()
