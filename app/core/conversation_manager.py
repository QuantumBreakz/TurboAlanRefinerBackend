"""
Conversation History Manager
Stores and manages chat conversation history per user to maintain context across requests.
"""
from typing import Dict, List, Optional, Any
from datetime import datetime
import json
import time

class ConversationHistory:
    """Stores conversation messages for a user"""
    def __init__(self, user_id: str):
        self.user_id = user_id
        self.messages: List[Dict[str, str]] = []  # List of {role: "user"/"assistant", content: "..."}
        self.created_at = time.time()
        self.updated_at = time.time()
        self.max_messages = 50  # Limit to prevent token bloat
    
    def add_message(self, role: str, content: str):
        """Add a message to the conversation history"""
        if not content or not content.strip():
            return
        
        self.messages.append({
            "role": role,
            "content": content.strip()
        })
        self.updated_at = time.time()
        
        # Keep only the last max_messages to prevent token bloat
        if len(self.messages) > self.max_messages:
            # Keep system message if present, then keep last max_messages-1
            system_messages = [m for m in self.messages if m["role"] == "system"]
            other_messages = [m for m in self.messages if m["role"] != "system"]
            self.messages = system_messages + other_messages[-(self.max_messages - len(system_messages)):]
    
    def get_messages(self, limit: Optional[int] = None) -> List[Dict[str, str]]:
        """Get conversation messages, optionally limited"""
        if limit:
            return self.messages[-limit:]
        return self.messages.copy()
    
    def clear(self):
        """Clear conversation history"""
        self.messages = []
        self.updated_at = time.time()
    
    def get_recent_context(self, num_messages: int = 10) -> List[Dict[str, str]]:
        """Get recent messages for context"""
        return self.messages[-num_messages:] if len(self.messages) > num_messages else self.messages.copy()
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for storage"""
        return {
            "user_id": self.user_id,
            "messages": self.messages,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
            "message_count": len(self.messages)
        }


class ConversationManager:
    """Manages conversation history for all users"""
    def __init__(self):
        self.conversations: Dict[str, ConversationHistory] = {}
        self.max_conversations = 1000  # Limit in-memory conversations
    
    def get_conversation(self, user_id: str) -> ConversationHistory:
        """Get or create conversation history for a user"""
        if user_id not in self.conversations:
            self.conversations[user_id] = ConversationHistory(user_id)
            
            # Cleanup old conversations if we exceed limit
            if len(self.conversations) > self.max_conversations:
                self._cleanup_old_conversations()
        
        return self.conversations[user_id]
    
    def add_message(self, user_id: str, role: str, content: str):
        """Add a message to user's conversation history"""
        conversation = self.get_conversation(user_id)
        conversation.add_message(role, content)
    
    def get_messages(self, user_id: str, limit: Optional[int] = None) -> List[Dict[str, str]]:
        """Get conversation messages for a user"""
        conversation = self.get_conversation(user_id)
        return conversation.get_messages(limit)
    
    def clear_conversation(self, user_id: str):
        """Clear conversation history for a user"""
        if user_id in self.conversations:
            self.conversations[user_id].clear()
    
    def get_recent_context(self, user_id: str, num_messages: int = 10) -> List[Dict[str, str]]:
        """Get recent conversation context for a user"""
        conversation = self.get_conversation(user_id)
        return conversation.get_recent_context(num_messages)
    
    def _cleanup_old_conversations(self):
        """Remove oldest conversations when limit is exceeded"""
        # Sort by updated_at and remove oldest
        sorted_convs = sorted(
            self.conversations.items(),
            key=lambda x: x[1].updated_at
        )
        
        # Remove oldest 10% of conversations
        remove_count = max(1, len(sorted_convs) // 10)
        for user_id, _ in sorted_convs[:remove_count]:
            del self.conversations[user_id]
    
    def save_to_mongodb(self, user_id: str, mongodb_db=None):
        """Save conversation to MongoDB if available"""
        if not mongodb_db or not mongodb_db.is_connected():
            return False
        
        try:
            conversation = self.get_conversation(user_id)
            collection = mongodb_db._db.conversations if mongodb_db._db else None
            
            if collection:
                collection.update_one(
                    {"user_id": user_id},
                    {
                        "$set": {
                            "messages": conversation.messages,
                            "updated_at": conversation.updated_at,
                            "message_count": len(conversation.messages)
                        },
                        "$setOnInsert": {
                            "user_id": user_id,
                            "created_at": conversation.created_at
                        }
                    },
                    upsert=True
                )
                return True
        except Exception as e:
            print(f"Failed to save conversation to MongoDB: {e}")
        
        return False
    
    def load_from_mongodb(self, user_id: str, mongodb_db=None):
        """Load conversation from MongoDB if available"""
        if not mongodb_db or not mongodb_db.is_connected():
            return False
        
        try:
            collection = mongodb_db._db.conversations if mongodb_db._db else None
            
            if collection:
                doc = collection.find_one({"user_id": user_id})
                if doc:
                    conversation = self.get_conversation(user_id)
                    conversation.messages = doc.get("messages", [])
                    conversation.created_at = doc.get("created_at", time.time())
                    conversation.updated_at = doc.get("updated_at", time.time())
                    return True
        except Exception as e:
            print(f"Failed to load conversation from MongoDB: {e}")
        
        return False


# Global conversation manager instance
conversation_manager = ConversationManager()

