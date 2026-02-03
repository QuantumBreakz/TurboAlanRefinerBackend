"""
Workspace & Collaborative Conversation Manager
Manages workspaces (document sessions) with multi-user support, contextful conversations,
and real-time collaboration capabilities.
"""
from typing import Dict, List, Optional, Any, Set
from datetime import datetime
from dataclasses import dataclass, field
import uuid
import time
import asyncio


@dataclass
class ChatMessage:
    """Enhanced chat message with sender and context information"""
    id: str
    conversation_id: str
    sender_id: str
    role: str  # "user" | "assistant" | "system"
    content: str
    timestamp: float
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "conversation_id": self.conversation_id,
            "sender_id": self.sender_id,
            "role": self.role,
            "content": self.content,
            "timestamp": self.timestamp,
            "metadata": self.metadata
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "ChatMessage":
        return cls(
            id=data.get("id", str(uuid.uuid4())),
            conversation_id=data.get("conversation_id", ""),
            sender_id=data.get("sender_id", "system"),
            role=data.get("role", "user"),
            content=data.get("content", ""),
            timestamp=data.get("timestamp", time.time()),
            metadata=data.get("metadata", {})
        )


@dataclass
class DocumentContext:
    """Context for a document/file within a workspace"""
    file_id: str
    job_id: Optional[str] = None
    filename: str = ""
    file_type: str = ""
    current_pass: int = 0
    refined_content: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "file_id": self.file_id,
            "job_id": self.job_id,
            "filename": self.filename,
            "file_type": self.file_type,
            "current_pass": self.current_pass,
            "refined_content": self.refined_content[:500] if self.refined_content else None,  # Truncate for storage
            "metadata": self.metadata
        }


@dataclass 
class Workspace:
    """
    A workspace represents a collaborative document session.
    It contains:
    - A conversation thread (messages)
    - Document context (files being worked on)
    - Participants (users who can access this workspace)
    """
    id: str
    name: str
    owner_id: str
    participants: Set[str] = field(default_factory=set)
    messages: List[ChatMessage] = field(default_factory=list)
    documents: Dict[str, DocumentContext] = field(default_factory=dict)
    active_document_id: Optional[str] = None
    created_at: float = field(default_factory=time.time)
    updated_at: float = field(default_factory=time.time)
    max_messages: int = 100
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def __post_init__(self):
        # Ensure owner is in participants
        self.participants.add(self.owner_id)
    
    def add_participant(self, user_id: str) -> bool:
        """Add a user to the workspace"""
        if user_id not in self.participants:
            self.participants.add(user_id)
            self.updated_at = time.time()
            return True
        return False
    
    def remove_participant(self, user_id: str) -> bool:
        """Remove a user from the workspace (owner cannot be removed)"""
        if user_id != self.owner_id and user_id in self.participants:
            self.participants.discard(user_id)
            self.updated_at = time.time()
            return True
        return False
    
    def is_participant(self, user_id: str) -> bool:
        """Check if a user is a participant"""
        return user_id in self.participants
    
    def add_message(self, sender_id: str, role: str, content: str, metadata: Optional[Dict] = None) -> ChatMessage:
        """Add a message to the workspace conversation"""
        if not content or not content.strip():
            raise ValueError("Message content cannot be empty")
        
        message = ChatMessage(
            id=str(uuid.uuid4()),
            conversation_id=self.id,
            sender_id=sender_id,
            role=role,
            content=content.strip(),
            timestamp=time.time(),
            metadata=metadata or {}
        )
        
        self.messages.append(message)
        self.updated_at = time.time()
        
        # Trim old messages if exceeding limit
        self._trim_messages()
        
        return message
    
    def _trim_messages(self):
        """Keep only the last max_messages, preserving system messages"""
        if len(self.messages) > self.max_messages:
            system_messages = [m for m in self.messages if m.role == "system"]
            other_messages = [m for m in self.messages if m.role != "system"]
            keep_count = self.max_messages - len(system_messages)
            self.messages = system_messages + other_messages[-keep_count:]
    
    def get_messages(self, limit: Optional[int] = None) -> List[ChatMessage]:
        """Get conversation messages, optionally limited"""
        if limit:
            return self.messages[-limit:]
        return self.messages.copy()
    
    def get_context_messages(self, num_messages: int = 15) -> List[Dict[str, str]]:
        """Get recent messages formatted for LLM context"""
        recent = self.messages[-num_messages:] if len(self.messages) > num_messages else self.messages
        return [{"role": m.role, "content": m.content} for m in recent]
    
    def add_document(self, file_id: str, filename: str, file_type: str, job_id: Optional[str] = None) -> DocumentContext:
        """Add a document to the workspace"""
        doc = DocumentContext(
            file_id=file_id,
            job_id=job_id,
            filename=filename,
            file_type=file_type
        )
        self.documents[file_id] = doc
        if not self.active_document_id:
            self.active_document_id = file_id
        self.updated_at = time.time()
        return doc
    
    def get_active_document(self) -> Optional[DocumentContext]:
        """Get the currently active document"""
        if self.active_document_id and self.active_document_id in self.documents:
            return self.documents[self.active_document_id]
        return None
    
    def set_active_document(self, file_id: str) -> bool:
        """Set the active document"""
        if file_id in self.documents:
            self.active_document_id = file_id
            self.updated_at = time.time()
            return True
        return False
    
    def get_document_context_summary(self) -> str:
        """Get a summary of document context for LLM prompts"""
        if not self.documents:
            return "No documents in workspace."
        
        active_doc = self.get_active_document()
        summaries = []
        
        for doc in self.documents.values():
            is_active = " (active)" if doc.file_id == self.active_document_id else ""
            status = f"Pass {doc.current_pass}" if doc.job_id else "Not processed"
            summaries.append(f"- {doc.filename}{is_active}: {doc.file_type}, {status}")
        
        return "Documents in workspace:\n" + "\n".join(summaries)
    
    def clear_messages(self):
        """Clear all messages except system messages"""
        self.messages = [m for m in self.messages if m.role == "system"]
        self.updated_at = time.time()
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert workspace to dictionary for storage"""
        return {
            "id": self.id,
            "name": self.name,
            "owner_id": self.owner_id,
            "participants": list(self.participants),
            "messages": [m.to_dict() for m in self.messages],
            "documents": {k: v.to_dict() for k, v in self.documents.items()},
            "active_document_id": self.active_document_id,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
            "metadata": self.metadata
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "Workspace":
        """Create workspace from dictionary"""
        workspace = cls(
            id=data.get("id", str(uuid.uuid4())),
            name=data.get("name", "Untitled Workspace"),
            owner_id=data.get("owner_id", "system"),
            participants=set(data.get("participants", [])),
            created_at=data.get("created_at", time.time()),
            updated_at=data.get("updated_at", time.time()),
            metadata=data.get("metadata", {})
        )
        
        # Restore messages
        for msg_data in data.get("messages", []):
            workspace.messages.append(ChatMessage.from_dict(msg_data))
        
        # Restore documents
        for file_id, doc_data in data.get("documents", {}).items():
            workspace.documents[file_id] = DocumentContext(
                file_id=doc_data.get("file_id", file_id),
                job_id=doc_data.get("job_id"),
                filename=doc_data.get("filename", ""),
                file_type=doc_data.get("file_type", ""),
                current_pass=doc_data.get("current_pass", 0),
                metadata=doc_data.get("metadata", {})
            )
        
        workspace.active_document_id = data.get("active_document_id")
        return workspace


class WorkspaceManager:
    """Manages all workspaces with persistence and real-time capabilities"""
    
    def __init__(self):
        self.workspaces: Dict[str, Workspace] = {}
        self.user_workspaces: Dict[str, Set[str]] = {}  # user_id -> set of workspace_ids
        self.max_workspaces_per_user = 50
        self.max_total_workspaces = 5000
        self._lock = asyncio.Lock()
        
        # Callbacks for real-time events
        self._message_callbacks: List[callable] = []
    
    def register_message_callback(self, callback: callable):
        """Register a callback to be called when a new message is added"""
        self._message_callbacks.append(callback)
    
    async def _notify_message_callbacks(self, workspace_id: str, message: ChatMessage):
        """Notify all registered callbacks of a new message"""
        for callback in self._message_callbacks:
            try:
                if asyncio.iscoroutinefunction(callback):
                    await callback(workspace_id, message)
                else:
                    callback(workspace_id, message)
            except Exception as e:
                print(f"Error in message callback: {e}")
    
    def create_workspace(
        self,
        owner_id: str,
        name: Optional[str] = None,
        workspace_id: Optional[str] = None
    ) -> Workspace:
        """Create a new workspace"""
        ws_id = workspace_id or str(uuid.uuid4())
        ws_name = name or f"Workspace {datetime.now().strftime('%Y-%m-%d %H:%M')}"
        
        workspace = Workspace(
            id=ws_id,
            name=ws_name,
            owner_id=owner_id
        )
        
        self.workspaces[ws_id] = workspace
        
        # Track user's workspaces
        if owner_id not in self.user_workspaces:
            self.user_workspaces[owner_id] = set()
        self.user_workspaces[owner_id].add(ws_id)
        
        # Cleanup if limits exceeded
        self._cleanup_if_needed(owner_id)
        
        # Auto-save to MongoDB
        try:
            from app.core.mongodb_db import db as mongodb_db
            self.save_workspace_to_mongodb(ws_id, mongodb_db)
        except Exception as e:
            print(f"Failed to auto-save workspace {ws_id}: {e}")
        
        return workspace
    
    def get_workspace(self, workspace_id: str) -> Optional[Workspace]:
        """Get a workspace by ID (with lazy loading from MongoDB)"""
        workspace = self.workspaces.get(workspace_id)
        
        # If not in memory, try to load from MongoDB
        if not workspace:
            try:
                from app.core.mongodb_db import db as mongodb_db
                workspace = self.load_workspace_from_mongodb(workspace_id, mongodb_db)
            except Exception as e:
                print(f"Failed to load workspace {workspace_id} from MongoDB: {e}")
        
        return workspace
    
    def get_or_create_workspace(
        self,
        workspace_id: str,
        owner_id: str,
        name: Optional[str] = None
    ) -> Workspace:
        """Get existing workspace or create new one"""
        workspace = self.get_workspace(workspace_id)
        if workspace:
            return workspace
        return self.create_workspace(owner_id, name, workspace_id)
    
    def get_user_workspaces(self, user_id: str) -> List[Workspace]:
        """Get all workspaces a user participates in (with lazy loading from MongoDB)"""
        # Try to load from MongoDB if user has no workspaces in memory
        if user_id not in self.user_workspaces or not self.user_workspaces[user_id]:
            try:
                from app.core.mongodb_db import db as mongodb_db
                mongodb_workspaces = self.load_user_workspaces_from_mongodb(user_id, mongodb_db)
                if mongodb_workspaces:
                    # Workspaces are already loaded into memory by load_user_workspaces_from_mongodb
                    pass
            except Exception as e:
                print(f"Failed to load workspaces for user {user_id} from MongoDB: {e}")
        
        workspaces = []
        for ws_id in self.user_workspaces.get(user_id, set()):
            ws = self.workspaces.get(ws_id)
            if ws and ws.is_participant(user_id):
                workspaces.append(ws)
        
        # Also check all workspaces in case user was added as participant elsewhere
        for ws in self.workspaces.values():
            if ws.is_participant(user_id) and ws not in workspaces:
                workspaces.append(ws)
                if user_id not in self.user_workspaces:
                    self.user_workspaces[user_id] = set()
                self.user_workspaces[user_id].add(ws.id)
        
        return sorted(workspaces, key=lambda w: w.updated_at, reverse=True)
    
    def delete_workspace(self, workspace_id: str, user_id: str) -> bool:
        """Delete a workspace (only owner can delete)"""
        workspace = self.workspaces.get(workspace_id)
        if not workspace or workspace.owner_id != user_id:
            return False
        
        # Remove from all users' workspace lists
        for participant_id in workspace.participants:
            if participant_id in self.user_workspaces:
                self.user_workspaces[participant_id].discard(workspace_id)
        
        del self.workspaces[workspace_id]
        return True
    
    def add_participant(self, workspace_id: str, user_id: str, added_by: str) -> bool:
        """Add a participant to a workspace"""
        workspace = self.workspaces.get(workspace_id)
        if not workspace:
            return False
        
        # Only owner or existing participants can add others
        if not workspace.is_participant(added_by):
            return False
        
        if workspace.add_participant(user_id):
            if user_id not in self.user_workspaces:
                self.user_workspaces[user_id] = set()
            self.user_workspaces[user_id].add(workspace_id)
            
            # Auto-save to MongoDB
            try:
                from app.core.mongodb_db import db as mongodb_db
                self.save_workspace_to_mongodb(workspace_id, mongodb_db)
            except Exception as e:
                print(f"Failed to auto-save workspace {workspace_id} after adding participant: {e}")
            
            return True
        return False
    
    async def add_message(
        self,
        workspace_id: str,
        sender_id: str,
        role: str,
        content: str,
        metadata: Optional[Dict] = None
    ) -> Optional[ChatMessage]:
        """Add a message to a workspace and notify callbacks"""
        workspace = self.workspaces.get(workspace_id)
        if not workspace:
            # Try to load from MongoDB if not in memory
            try:
                from app.core.mongodb_db import db as mongodb_db
                workspace = self.load_workspace_from_mongodb(workspace_id, mongodb_db)
            except Exception:
                pass
            
            if not workspace:
                return None
        
        # Check if sender is a participant (or system)
        if sender_id != "system" and role != "assistant" and not workspace.is_participant(sender_id):
            return None
        
        message = workspace.add_message(sender_id, role, content, metadata)
        
        # Notify real-time callbacks
        await self._notify_message_callbacks(workspace_id, message)
        
        # Auto-save to MongoDB after adding message
        try:
            from app.core.mongodb_db import db as mongodb_db
            self.save_workspace_to_mongodb(workspace_id, mongodb_db)
        except Exception as e:
            print(f"Failed to auto-save workspace {workspace_id} after message: {e}")
        
        return message
    
    def get_conversation_context(
        self,
        workspace_id: str,
        num_messages: int = 15,
        include_document_context: bool = True
    ) -> List[Dict[str, str]]:
        """Get conversation context formatted for LLM"""
        workspace = self.workspaces.get(workspace_id)
        if not workspace:
            return []
        
        context = []
        
        # Add document context as system message if available
        if include_document_context and workspace.documents:
            doc_summary = workspace.get_document_context_summary()
            context.append({
                "role": "system",
                "content": f"Current workspace context:\n{doc_summary}"
            })
        
        # Add recent messages
        context.extend(workspace.get_context_messages(num_messages))
        
        return context
    
    def _cleanup_if_needed(self, user_id: str):
        """Cleanup old workspaces if limits exceeded"""
        # Per-user cleanup
        user_ws_ids = self.user_workspaces.get(user_id, set())
        if len(user_ws_ids) > self.max_workspaces_per_user:
            # Get user's workspaces sorted by updated_at
            user_workspaces = [
                self.workspaces[ws_id]
                for ws_id in user_ws_ids
                if ws_id in self.workspaces
            ]
            user_workspaces.sort(key=lambda w: w.updated_at)
            
            # Remove oldest workspaces
            remove_count = len(user_workspaces) - self.max_workspaces_per_user + 5
            for ws in user_workspaces[:remove_count]:
                if ws.owner_id == user_id:
                    self.delete_workspace(ws.id, user_id)
        
        # Global cleanup
        if len(self.workspaces) > self.max_total_workspaces:
            all_workspaces = sorted(
                self.workspaces.values(),
                key=lambda w: w.updated_at
            )
            remove_count = len(all_workspaces) - self.max_total_workspaces + 100
            for ws in all_workspaces[:remove_count]:
                # Remove from all users
                for uid in list(ws.participants):
                    if uid in self.user_workspaces:
                        self.user_workspaces[uid].discard(ws.id)
                del self.workspaces[ws.id]
    
    # MongoDB persistence methods
    def save_workspace_to_mongodb(self, workspace_id: str, mongodb_db=None) -> bool:
        """Save workspace to MongoDB"""
        if not mongodb_db or not mongodb_db.is_connected():
            return False
        
        workspace = self.workspaces.get(workspace_id)
        if not workspace:
            return False
        
        try:
            collection = mongodb_db._db.workspaces if mongodb_db._db is not None else None
            if collection is not None:
                collection.update_one(
                    {"id": workspace_id},
                    {"$set": workspace.to_dict()},
                    upsert=True
                )
                return True
        except Exception as e:
            print(f"Failed to save workspace to MongoDB: {e}")
        
        return False
    
    def load_workspace_from_mongodb(self, workspace_id: str, mongodb_db=None) -> Optional[Workspace]:
        """Load workspace from MongoDB"""
        if not mongodb_db or not mongodb_db.is_connected():
            return None
        
        try:
            collection = mongodb_db._db.workspaces if mongodb_db._db is not None else None
            if collection is not None:
                doc = collection.find_one({"id": workspace_id})
                if doc:
                    workspace = Workspace.from_dict(doc)
                    self.workspaces[workspace_id] = workspace
                    
                    # Update user_workspaces index
                    for user_id in workspace.participants:
                        if user_id not in self.user_workspaces:
                            self.user_workspaces[user_id] = set()
                        self.user_workspaces[user_id].add(workspace_id)
                    
                    return workspace
        except Exception as e:
            print(f"Failed to load workspace from MongoDB: {e}")
        
        return None
    
    def load_user_workspaces_from_mongodb(self, user_id: str, mongodb_db=None) -> List[Workspace]:
        """Load all workspaces for a user from MongoDB"""
        if not mongodb_db or not mongodb_db.is_connected():
            return []
        
        workspaces = []
        try:
            collection = mongodb_db._db.workspaces if mongodb_db._db is not None else None
            if collection is not None:
                # Find workspaces where user is a participant
                docs = collection.find({"participants": user_id}).sort("updated_at", -1).limit(50)
                for doc in docs:
                    workspace = Workspace.from_dict(doc)
                    self.workspaces[workspace.id] = workspace
                    
                    # Update user_workspaces index
                    for uid in workspace.participants:
                        if uid not in self.user_workspaces:
                            self.user_workspaces[uid] = set()
                        self.user_workspaces[uid].add(workspace.id)
                    
                    workspaces.append(workspace)
        except Exception as e:
            print(f"Failed to load user workspaces from MongoDB: {e}")
        
        return workspaces


# Global workspace manager instance
workspace_manager = WorkspaceManager()


# Backward compatibility: Create a shim for the old ConversationManager interface
class LegacyConversationAdapter:
    """
    Adapter to maintain backward compatibility with code using the old ConversationManager.
    Maps user_id to a default workspace per user.
    """
    
    def __init__(self, workspace_manager: WorkspaceManager):
        self._workspace_manager = workspace_manager
        self._user_default_workspaces: Dict[str, str] = {}
    
    def _get_default_workspace(self, user_id: str) -> Workspace:
        """Get or create the default workspace for a user"""
        if user_id in self._user_default_workspaces:
            ws_id = self._user_default_workspaces[user_id]
            ws = self._workspace_manager.get_workspace(ws_id)
            if ws:
                return ws
        
        # Create default workspace
        ws = self._workspace_manager.create_workspace(
            owner_id=user_id,
            name=f"Default Conversation - {user_id}"
        )
        self._user_default_workspaces[user_id] = ws.id
        return ws
    
    def get_conversation(self, user_id: str):
        """Get conversation (returns workspace for compatibility)"""
        return self._get_default_workspace(user_id)
    
    def add_message(self, user_id: str, role: str, content: str):
        """Add message to user's default workspace"""
        ws = self._get_default_workspace(user_id)
        ws.add_message(user_id, role, content)
    
    def get_messages(self, user_id: str, limit: Optional[int] = None) -> List[Dict[str, str]]:
        """Get messages from user's default workspace"""
        ws = self._get_default_workspace(user_id)
        messages = ws.get_messages(limit)
        return [{"role": m.role, "content": m.content} for m in messages]
    
    def clear_conversation(self, user_id: str):
        """Clear user's default workspace messages"""
        ws = self._get_default_workspace(user_id)
        ws.clear_messages()
    
    def get_recent_context(self, user_id: str, num_messages: int = 10) -> List[Dict[str, str]]:
        """Get recent context from user's default workspace"""
        ws = self._get_default_workspace(user_id)
        return ws.get_context_messages(num_messages)
    
    def save_to_mongodb(self, user_id: str, mongodb_db=None):
        """Save to MongoDB"""
        if user_id in self._user_default_workspaces:
            ws_id = self._user_default_workspaces[user_id]
            return self._workspace_manager.save_workspace_to_mongodb(ws_id, mongodb_db)
        return False
    
    def load_from_mongodb(self, user_id: str, mongodb_db=None):
        """Load from MongoDB"""
        # This is handled by the workspace manager
        return False


# Create legacy adapter for backward compatibility
legacy_conversation_adapter = LegacyConversationAdapter(workspace_manager)
