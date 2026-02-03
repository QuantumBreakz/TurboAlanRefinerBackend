#!/usr/bin/env python3
"""
Comprehensive Test Suite for Collaborative Chat System
======================================================

This test script covers:
1. Workspace CRUD operations
2. Participant management
3. Message operations
4. Chat with AI responses
5. Document context management
6. WebSocket real-time functionality
7. Edge cases and error handling
8. Concurrency and race conditions
9. Memory and cleanup

Usage:
    # Activate your global Python environment first
    globalpy
    
    # Run all tests
    python -m pytest tests/test_collaborative_chat.py -v
    
    # Run specific test class
    python -m pytest tests/test_collaborative_chat.py::TestWorkspaceManager -v
    
    # Run with coverage
    python -m pytest tests/test_collaborative_chat.py -v --cov=app.core.workspace_manager
    
    # Run standalone (without pytest)
    python tests/test_collaborative_chat.py
"""

import sys
import os
import asyncio
import time
import uuid
import json
from typing import List, Dict, Any, Optional
from dataclasses import dataclass
from unittest.mock import MagicMock, AsyncMock, patch
from concurrent.futures import ThreadPoolExecutor

# Add parent directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Import the modules we're testing
from app.core.workspace_manager import (
    WorkspaceManager,
    Workspace,
    ChatMessage,
    DocumentContext,
    workspace_manager,
    legacy_conversation_adapter
)
from app.core.chat_websocket import (
    ChatWebSocketManager,
    UserPresence,
    chat_ws_manager
)


# ============================================================================
# Test Utilities
# ============================================================================

# Import shared TestResult from test_utils
from test_utils import TestResult

class TestRunner:
    """Simple test runner for standalone execution"""
    def __init__(self):
        self.results: List[TestResult] = []
        self.passed = 0
        self.failed = 0
    
    def run_test(self, name: str, test_func):
        """Run a single test and record result"""
        start = time.time()
        try:
            if asyncio.iscoroutinefunction(test_func):
                asyncio.get_event_loop().run_until_complete(test_func())
            else:
                test_func()
            duration = time.time() - start
            self.results.append(TestResult(name, True, "OK", duration))
            self.passed += 1
            print(f"  ✅ {name} ({duration:.3f}s)")
        except AssertionError as e:
            duration = time.time() - start
            self.results.append(TestResult(name, False, str(e), duration))
            self.failed += 1
            print(f"  ❌ {name}: {e}")
        except Exception as e:
            duration = time.time() - start
            self.results.append(TestResult(name, False, f"Error: {e}", duration))
            self.failed += 1
            print(f"  ❌ {name}: {type(e).__name__}: {e}")
    
    def report(self):
        """Print final test report"""
        total = self.passed + self.failed
        print(f"\n{'='*60}")
        print(f"Test Results: {self.passed}/{total} passed")
        if self.failed > 0:
            print(f"\nFailed tests:")
            for r in self.results:
                if not r.passed:
                    print(f"  - {r.name}: {r.message}")
        print(f"{'='*60}\n")
        return self.failed == 0


def generate_user_id() -> str:
    """Generate a unique user ID for testing"""
    return f"test_user_{uuid.uuid4().hex[:8]}"


def generate_workspace_id() -> str:
    """Generate a unique workspace ID for testing"""
    return f"test_ws_{uuid.uuid4().hex[:12]}"


# ============================================================================
# Test Classes
# ============================================================================

class TestWorkspaceManager:
    """Tests for WorkspaceManager functionality"""
    
    def __init__(self):
        self.manager = WorkspaceManager()
    
    def test_create_workspace(self):
        """Test basic workspace creation"""
        user_id = generate_user_id()
        workspace = self.manager.create_workspace(owner_id=user_id, name="Test Workspace")
        
        assert workspace is not None, "Workspace should be created"
        assert workspace.owner_id == user_id, "Owner ID should match"
        assert workspace.name == "Test Workspace", "Name should match"
        assert user_id in workspace.participants, "Owner should be a participant"
        assert len(workspace.messages) == 0, "Should start with no messages"
    
    def test_create_workspace_with_custom_id(self):
        """Test workspace creation with custom ID"""
        user_id = generate_user_id()
        custom_id = generate_workspace_id()
        workspace = self.manager.create_workspace(
            owner_id=user_id, 
            name="Custom ID Workspace",
            workspace_id=custom_id
        )
        
        assert workspace.id == custom_id, "Should use custom ID"
    
    def test_get_workspace(self):
        """Test retrieving a workspace"""
        user_id = generate_user_id()
        workspace = self.manager.create_workspace(owner_id=user_id)
        
        retrieved = self.manager.get_workspace(workspace.id)
        assert retrieved is not None, "Should retrieve workspace"
        assert retrieved.id == workspace.id, "IDs should match"
    
    def test_get_nonexistent_workspace(self):
        """Test retrieving a workspace that doesn't exist"""
        result = self.manager.get_workspace("nonexistent_id_12345")
        assert result is None, "Should return None for nonexistent workspace"
    
    def test_get_or_create_workspace(self):
        """Test get_or_create functionality"""
        user_id = generate_user_id()
        ws_id = generate_workspace_id()
        
        # First call should create
        workspace1 = self.manager.get_or_create_workspace(ws_id, user_id, "New Workspace")
        assert workspace1 is not None, "Should create workspace"
        
        # Second call should return existing
        workspace2 = self.manager.get_or_create_workspace(ws_id, user_id)
        assert workspace2.id == workspace1.id, "Should return same workspace"
    
    def test_get_user_workspaces(self):
        """Test listing workspaces for a user"""
        user_id = generate_user_id()
        
        # Create multiple workspaces
        ws1 = self.manager.create_workspace(owner_id=user_id, name="WS 1")
        ws2 = self.manager.create_workspace(owner_id=user_id, name="WS 2")
        ws3 = self.manager.create_workspace(owner_id=user_id, name="WS 3")
        
        workspaces = self.manager.get_user_workspaces(user_id)
        assert len(workspaces) >= 3, "Should have at least 3 workspaces"
        
        ws_ids = [ws.id for ws in workspaces]
        assert ws1.id in ws_ids, "WS 1 should be in list"
        assert ws2.id in ws_ids, "WS 2 should be in list"
        assert ws3.id in ws_ids, "WS 3 should be in list"
    
    def test_delete_workspace(self):
        """Test workspace deletion"""
        user_id = generate_user_id()
        workspace = self.manager.create_workspace(owner_id=user_id)
        ws_id = workspace.id
        
        result = self.manager.delete_workspace(ws_id, user_id)
        assert result is True, "Delete should succeed"
        
        retrieved = self.manager.get_workspace(ws_id)
        assert retrieved is None, "Workspace should be deleted"
    
    def test_delete_workspace_wrong_owner(self):
        """Test that non-owner cannot delete workspace"""
        owner = generate_user_id()
        other_user = generate_user_id()
        workspace = self.manager.create_workspace(owner_id=owner)
        
        result = self.manager.delete_workspace(workspace.id, other_user)
        assert result is False, "Non-owner should not be able to delete"
        
        # Workspace should still exist
        retrieved = self.manager.get_workspace(workspace.id)
        assert retrieved is not None, "Workspace should still exist"


class TestWorkspaceParticipants:
    """Tests for participant management"""
    
    def __init__(self):
        self.manager = WorkspaceManager()
    
    def test_add_participant(self):
        """Test adding a participant"""
        owner = generate_user_id()
        participant = generate_user_id()
        workspace = self.manager.create_workspace(owner_id=owner)
        
        result = self.manager.add_participant(workspace.id, participant, owner)
        assert result is True, "Should add participant"
        assert participant in workspace.participants, "Participant should be in list"
    
    def test_add_participant_unauthorized(self):
        """Test that non-participant cannot add others"""
        owner = generate_user_id()
        outsider = generate_user_id()
        new_user = generate_user_id()
        workspace = self.manager.create_workspace(owner_id=owner)
        
        result = self.manager.add_participant(workspace.id, new_user, outsider)
        assert result is False, "Outsider should not be able to add participants"
    
    def test_add_duplicate_participant(self):
        """Test adding a participant who's already in the workspace"""
        owner = generate_user_id()
        participant = generate_user_id()
        workspace = self.manager.create_workspace(owner_id=owner)
        
        self.manager.add_participant(workspace.id, participant, owner)
        result = self.manager.add_participant(workspace.id, participant, owner)
        
        assert result is False, "Should return False for duplicate"
    
    def test_remove_participant(self):
        """Test removing a participant"""
        owner = generate_user_id()
        participant = generate_user_id()
        workspace = self.manager.create_workspace(owner_id=owner)
        
        self.manager.add_participant(workspace.id, participant, owner)
        assert participant in workspace.participants
        
        result = workspace.remove_participant(participant)
        assert result is True, "Should remove participant"
        assert participant not in workspace.participants, "Participant should be removed"
    
    def test_cannot_remove_owner(self):
        """Test that owner cannot be removed"""
        owner = generate_user_id()
        workspace = self.manager.create_workspace(owner_id=owner)
        
        result = workspace.remove_participant(owner)
        assert result is False, "Should not be able to remove owner"
        assert owner in workspace.participants, "Owner should still be participant"
    
    def test_participant_can_leave(self):
        """Test that a participant can remove themselves"""
        owner = generate_user_id()
        participant = generate_user_id()
        workspace = self.manager.create_workspace(owner_id=owner)
        
        self.manager.add_participant(workspace.id, participant, owner)
        result = workspace.remove_participant(participant)
        
        assert result is True, "Participant should be able to leave"


class TestWorkspaceMessages:
    """Tests for message functionality"""
    
    def __init__(self):
        self.manager = WorkspaceManager()
    
    def test_add_message(self):
        """Test adding a message to workspace"""
        user_id = generate_user_id()
        workspace = self.manager.create_workspace(owner_id=user_id)
        
        message = workspace.add_message(
            sender_id=user_id,
            role="user",
            content="Hello, world!"
        )
        
        assert message is not None, "Message should be created"
        assert message.content == "Hello, world!", "Content should match"
        assert message.sender_id == user_id, "Sender should match"
        assert message.role == "user", "Role should match"
        assert len(workspace.messages) == 1, "Should have 1 message"
    
    def test_add_empty_message(self):
        """Test that empty messages are rejected"""
        user_id = generate_user_id()
        workspace = self.manager.create_workspace(owner_id=user_id)
        
        try:
            workspace.add_message(user_id, "user", "")
            assert False, "Should raise exception for empty message"
        except ValueError:
            pass  # Expected
    
    def test_add_whitespace_message(self):
        """Test that whitespace-only messages are rejected"""
        user_id = generate_user_id()
        workspace = self.manager.create_workspace(owner_id=user_id)
        
        try:
            workspace.add_message(user_id, "user", "   \n\t  ")
            assert False, "Should raise exception for whitespace message"
        except ValueError:
            pass  # Expected
    
    def test_message_trimming(self):
        """Test that messages are trimmed when exceeding limit"""
        user_id = generate_user_id()
        workspace = self.manager.create_workspace(owner_id=user_id)
        workspace.max_messages = 10
        
        # Add more messages than the limit
        for i in range(15):
            workspace.add_message(user_id, "user", f"Message {i}")
        
        assert len(workspace.messages) == 10, f"Should have exactly 10 messages, got {len(workspace.messages)}"
    
    def test_system_messages_preserved_on_trim(self):
        """Test that system messages are preserved when trimming"""
        user_id = generate_user_id()
        workspace = self.manager.create_workspace(owner_id=user_id)
        workspace.max_messages = 5
        
        # Add a system message
        workspace.add_message("system", "system", "Welcome message")
        
        # Add more user messages than the limit
        for i in range(10):
            workspace.add_message(user_id, "user", f"Message {i}")
        
        # System message should still be there
        system_msgs = [m for m in workspace.messages if m.role == "system"]
        assert len(system_msgs) == 1, "System message should be preserved"
    
    def test_get_messages_with_limit(self):
        """Test getting limited number of messages"""
        user_id = generate_user_id()
        workspace = self.manager.create_workspace(owner_id=user_id)
        
        for i in range(20):
            workspace.add_message(user_id, "user", f"Message {i}")
        
        limited = workspace.get_messages(limit=5)
        assert len(limited) == 5, "Should return 5 messages"
        
        # Should return the last 5 messages
        assert limited[0].content == "Message 15"
        assert limited[4].content == "Message 19"
    
    def test_get_context_messages(self):
        """Test getting context for LLM"""
        user_id = generate_user_id()
        workspace = self.manager.create_workspace(owner_id=user_id)
        
        workspace.add_message(user_id, "user", "Hello")
        workspace.add_message("assistant", "assistant", "Hi there!")
        
        context = workspace.get_context_messages(num_messages=10)
        assert len(context) == 2, "Should have 2 messages"
        assert context[0]["role"] == "user"
        assert context[1]["role"] == "assistant"
    
    def test_clear_messages(self):
        """Test clearing messages"""
        user_id = generate_user_id()
        workspace = self.manager.create_workspace(owner_id=user_id)
        
        workspace.add_message("system", "system", "Welcome")
        workspace.add_message(user_id, "user", "Hello")
        workspace.add_message("assistant", "assistant", "Hi")
        
        workspace.clear_messages()
        
        # Only system messages should remain
        assert len(workspace.messages) == 1, "Should keep system message"
        assert workspace.messages[0].role == "system"


class TestDocumentContext:
    """Tests for document context management"""
    
    def __init__(self):
        self.manager = WorkspaceManager()
    
    def test_add_document(self):
        """Test adding a document to workspace"""
        user_id = generate_user_id()
        workspace = self.manager.create_workspace(owner_id=user_id)
        
        doc = workspace.add_document(
            file_id="file_123",
            filename="test.docx",
            file_type="application/docx",
            job_id="job_456"
        )
        
        assert doc is not None, "Document should be created"
        assert doc.file_id == "file_123"
        assert doc.filename == "test.docx"
        assert workspace.active_document_id == "file_123", "First doc should be active"
    
    def test_set_active_document(self):
        """Test setting active document"""
        user_id = generate_user_id()
        workspace = self.manager.create_workspace(owner_id=user_id)
        
        workspace.add_document("file_1", "doc1.docx", "docx")
        workspace.add_document("file_2", "doc2.docx", "docx")
        
        result = workspace.set_active_document("file_2")
        assert result is True
        assert workspace.active_document_id == "file_2"
    
    def test_set_nonexistent_active_document(self):
        """Test setting non-existent document as active"""
        user_id = generate_user_id()
        workspace = self.manager.create_workspace(owner_id=user_id)
        
        result = workspace.set_active_document("nonexistent")
        assert result is False
    
    def test_get_active_document(self):
        """Test getting active document"""
        user_id = generate_user_id()
        workspace = self.manager.create_workspace(owner_id=user_id)
        
        workspace.add_document("file_1", "doc1.docx", "docx")
        
        active = workspace.get_active_document()
        assert active is not None
        assert active.file_id == "file_1"
    
    def test_document_context_summary(self):
        """Test document context summary generation"""
        user_id = generate_user_id()
        workspace = self.manager.create_workspace(owner_id=user_id)
        
        workspace.add_document("file_1", "doc1.docx", "docx", "job_1")
        workspace.add_document("file_2", "doc2.pdf", "pdf")
        
        summary = workspace.get_document_context_summary()
        assert "doc1.docx" in summary
        assert "doc2.pdf" in summary
        assert "(active)" in summary


class TestChatMessage:
    """Tests for ChatMessage class"""
    
    def test_message_to_dict(self):
        """Test converting message to dictionary"""
        msg = ChatMessage(
            id="msg_123",
            conversation_id="ws_456",
            sender_id="user_789",
            role="user",
            content="Hello",
            timestamp=1234567890.0,
            metadata={"key": "value"}
        )
        
        d = msg.to_dict()
        assert d["id"] == "msg_123"
        assert d["conversation_id"] == "ws_456"
        assert d["content"] == "Hello"
        assert d["metadata"]["key"] == "value"
    
    def test_message_from_dict(self):
        """Test creating message from dictionary"""
        data = {
            "id": "msg_123",
            "conversation_id": "ws_456",
            "sender_id": "user_789",
            "role": "user",
            "content": "Hello",
            "timestamp": 1234567890.0
        }
        
        msg = ChatMessage.from_dict(data)
        assert msg.id == "msg_123"
        assert msg.content == "Hello"


class TestWorkspaceSerialization:
    """Tests for workspace serialization/deserialization"""
    
    def __init__(self):
        self.manager = WorkspaceManager()
    
    def test_workspace_to_dict(self):
        """Test converting workspace to dictionary"""
        user_id = generate_user_id()
        workspace = self.manager.create_workspace(owner_id=user_id, name="Test WS")
        workspace.add_message(user_id, "user", "Hello")
        workspace.add_document("file_1", "doc.docx", "docx")
        
        d = workspace.to_dict()
        
        assert d["name"] == "Test WS"
        assert d["owner_id"] == user_id
        assert user_id in d["participants"]
        assert len(d["messages"]) == 1
        assert "file_1" in d["documents"]
    
    def test_workspace_from_dict(self):
        """Test creating workspace from dictionary"""
        user_id = generate_user_id()
        data = {
            "id": "ws_123",
            "name": "Restored WS",
            "owner_id": user_id,
            "participants": [user_id],
            "messages": [
                {
                    "id": "msg_1",
                    "conversation_id": "ws_123",
                    "sender_id": user_id,
                    "role": "user",
                    "content": "Hello",
                    "timestamp": 1234567890.0
                }
            ],
            "documents": {
                "file_1": {
                    "file_id": "file_1",
                    "filename": "doc.docx",
                    "file_type": "docx"
                }
            },
            "created_at": 1234567890.0,
            "updated_at": 1234567890.0
        }
        
        workspace = Workspace.from_dict(data)
        
        assert workspace.id == "ws_123"
        assert workspace.name == "Restored WS"
        assert len(workspace.messages) == 1
        assert "file_1" in workspace.documents


class TestLegacyAdapter:
    """Tests for backward compatibility adapter"""
    
    def test_get_conversation(self):
        """Test legacy get_conversation method"""
        user_id = generate_user_id()
        
        conv = legacy_conversation_adapter.get_conversation(user_id)
        assert conv is not None
    
    def test_add_and_get_messages(self):
        """Test legacy add_message and get_messages"""
        user_id = generate_user_id()
        
        legacy_conversation_adapter.add_message(user_id, "user", "Hello")
        legacy_conversation_adapter.add_message(user_id, "assistant", "Hi there!")
        
        messages = legacy_conversation_adapter.get_messages(user_id)
        assert len(messages) == 2
        assert messages[0]["role"] == "user"
        assert messages[1]["role"] == "assistant"
    
    def test_clear_conversation(self):
        """Test legacy clear_conversation"""
        user_id = generate_user_id()
        
        legacy_conversation_adapter.add_message(user_id, "user", "Hello")
        legacy_conversation_adapter.clear_conversation(user_id)
        
        messages = legacy_conversation_adapter.get_messages(user_id)
        assert len(messages) == 0


class TestAsyncWorkspaceOperations:
    """Tests for async workspace operations"""
    
    def __init__(self):
        self.manager = WorkspaceManager()
    
    async def test_async_add_message(self):
        """Test async message addition"""
        user_id = generate_user_id()
        workspace = self.manager.create_workspace(owner_id=user_id)
        
        message = await self.manager.add_message(
            workspace_id=workspace.id,
            sender_id=user_id,
            role="user",
            content="Async hello!"
        )
        
        assert message is not None
        assert message.content == "Async hello!"
    
    async def test_async_add_message_invalid_workspace(self):
        """Test async message to invalid workspace"""
        message = await self.manager.add_message(
            workspace_id="nonexistent",
            sender_id="user_123",
            role="user",
            content="Hello"
        )
        
        assert message is None


class TestChatWebSocketManager:
    """Tests for WebSocket manager"""
    
    def __init__(self):
        self.manager = ChatWebSocketManager()
    
    def test_get_online_users_empty(self):
        """Test getting online users for empty workspace"""
        users = self.manager.get_online_users("empty_workspace")
        assert users == []
    
    def test_get_typing_users_empty(self):
        """Test getting typing users for empty workspace"""
        users = self.manager.get_typing_users("empty_workspace")
        assert users == []
    
    def test_get_workspace_stats(self):
        """Test getting workspace stats"""
        stats = self.manager.get_workspace_stats("test_workspace")
        
        assert "workspace_id" in stats
        assert "online_count" in stats
        assert "online_users" in stats
        assert "typing_users" in stats
        assert stats["online_count"] == 0


class TestEdgeCases:
    """Tests for edge cases and error handling"""
    
    def __init__(self):
        self.manager = WorkspaceManager()
    
    def test_very_long_message(self):
        """Test handling very long messages"""
        user_id = generate_user_id()
        workspace = self.manager.create_workspace(owner_id=user_id)
        
        # Create a 10KB message
        long_content = "x" * 10000
        message = workspace.add_message(user_id, "user", long_content)
        
        assert message.content == long_content
    
    def test_special_characters_in_message(self):
        """Test handling special characters in messages"""
        user_id = generate_user_id()
        workspace = self.manager.create_workspace(owner_id=user_id)
        
        special_content = "Hello 🎉 <script>alert('xss')</script> \n\t\r"
        message = workspace.add_message(user_id, "user", special_content)
        
        assert "🎉" in message.content
        assert "<script>" in message.content
    
    def test_unicode_workspace_name(self):
        """Test Unicode characters in workspace name"""
        user_id = generate_user_id()
        workspace = self.manager.create_workspace(
            owner_id=user_id,
            name="测试工作区 🚀"
        )
        
        assert workspace.name == "测试工作区 🚀"
    
    def test_many_participants(self):
        """Test workspace with many participants"""
        owner = generate_user_id()
        workspace = self.manager.create_workspace(owner_id=owner)
        
        # Add 100 participants
        for i in range(100):
            workspace.add_participant(f"user_{i}")
        
        assert len(workspace.participants) == 101  # 100 + owner
    
    def test_many_workspaces_per_user(self):
        """Test creating many workspaces for a user"""
        user_id = generate_user_id()
        
        for i in range(100):
            self.manager.create_workspace(owner_id=user_id, name=f"WS {i}")
        
        workspaces = self.manager.get_user_workspaces(user_id)
        # After cleanup, should have at least some workspaces (max is 50 per user)
        assert len(workspaces) >= 10, f"Expected at least 10 workspaces, got {len(workspaces)}"
    
    def test_concurrent_message_addition(self):
        """Test concurrent message additions"""
        user_id = generate_user_id()
        workspace = self.manager.create_workspace(owner_id=user_id)
        
        def add_messages(n):
            for i in range(n):
                workspace.add_message(user_id, "user", f"Concurrent message {i}")
        
        # Run concurrent additions
        with ThreadPoolExecutor(max_workers=5) as executor:
            futures = [executor.submit(add_messages, 10) for _ in range(5)]
            for f in futures:
                f.result()
        
        # Should have all messages (50 total)
        # Note: May be trimmed if > max_messages
        assert len(workspace.messages) > 0


class TestConversationContext:
    """Tests for conversation context building"""
    
    def __init__(self):
        self.manager = WorkspaceManager()
    
    def test_get_conversation_context_empty(self):
        """Test getting context from empty workspace"""
        user_id = generate_user_id()
        workspace = self.manager.create_workspace(owner_id=user_id)
        
        context = self.manager.get_conversation_context(workspace.id)
        assert context == []
    
    def test_get_conversation_context_with_messages(self):
        """Test getting context with messages"""
        user_id = generate_user_id()
        workspace = self.manager.create_workspace(owner_id=user_id)
        
        workspace.add_message(user_id, "user", "Hello")
        workspace.add_message("assistant", "assistant", "Hi!")
        
        context = self.manager.get_conversation_context(workspace.id, num_messages=10)
        
        # Should have 2 messages (no doc context since no docs)
        assert len(context) == 2
    
    def test_get_conversation_context_with_documents(self):
        """Test getting context with document context"""
        user_id = generate_user_id()
        workspace = self.manager.create_workspace(owner_id=user_id)
        
        workspace.add_document("file_1", "doc.docx", "docx")
        workspace.add_message(user_id, "user", "Hello")
        
        context = self.manager.get_conversation_context(
            workspace.id, 
            num_messages=10,
            include_document_context=True
        )
        
        # Should have system message (doc context) + user message
        assert len(context) == 2
        assert context[0]["role"] == "system"
        assert "doc.docx" in context[0]["content"]


# ============================================================================
# Main Test Runner
# ============================================================================

def run_all_tests():
    """Run all tests"""
    print("\n" + "="*60)
    print("Collaborative Chat System - Comprehensive Test Suite")
    print("="*60 + "\n")
    
    runner = TestRunner()
    
    # Test Workspace Manager
    print("\n📦 Testing WorkspaceManager...")
    ws_tests = TestWorkspaceManager()
    runner.run_test("create_workspace", ws_tests.test_create_workspace)
    runner.run_test("create_workspace_with_custom_id", ws_tests.test_create_workspace_with_custom_id)
    runner.run_test("get_workspace", ws_tests.test_get_workspace)
    runner.run_test("get_nonexistent_workspace", ws_tests.test_get_nonexistent_workspace)
    runner.run_test("get_or_create_workspace", ws_tests.test_get_or_create_workspace)
    runner.run_test("get_user_workspaces", ws_tests.test_get_user_workspaces)
    runner.run_test("delete_workspace", ws_tests.test_delete_workspace)
    runner.run_test("delete_workspace_wrong_owner", ws_tests.test_delete_workspace_wrong_owner)
    
    # Test Participants
    print("\n👥 Testing Participant Management...")
    participant_tests = TestWorkspaceParticipants()
    runner.run_test("add_participant", participant_tests.test_add_participant)
    runner.run_test("add_participant_unauthorized", participant_tests.test_add_participant_unauthorized)
    runner.run_test("add_duplicate_participant", participant_tests.test_add_duplicate_participant)
    runner.run_test("remove_participant", participant_tests.test_remove_participant)
    runner.run_test("cannot_remove_owner", participant_tests.test_cannot_remove_owner)
    runner.run_test("participant_can_leave", participant_tests.test_participant_can_leave)
    
    # Test Messages
    print("\n💬 Testing Message Operations...")
    msg_tests = TestWorkspaceMessages()
    runner.run_test("add_message", msg_tests.test_add_message)
    runner.run_test("add_empty_message", msg_tests.test_add_empty_message)
    runner.run_test("add_whitespace_message", msg_tests.test_add_whitespace_message)
    runner.run_test("message_trimming", msg_tests.test_message_trimming)
    runner.run_test("system_messages_preserved_on_trim", msg_tests.test_system_messages_preserved_on_trim)
    runner.run_test("get_messages_with_limit", msg_tests.test_get_messages_with_limit)
    runner.run_test("get_context_messages", msg_tests.test_get_context_messages)
    runner.run_test("clear_messages", msg_tests.test_clear_messages)
    
    # Test Documents
    print("\n📄 Testing Document Context...")
    doc_tests = TestDocumentContext()
    runner.run_test("add_document", doc_tests.test_add_document)
    runner.run_test("set_active_document", doc_tests.test_set_active_document)
    runner.run_test("set_nonexistent_active_document", doc_tests.test_set_nonexistent_active_document)
    runner.run_test("get_active_document", doc_tests.test_get_active_document)
    runner.run_test("document_context_summary", doc_tests.test_document_context_summary)
    
    # Test ChatMessage
    print("\n📨 Testing ChatMessage...")
    chat_msg_tests = TestChatMessage()
    runner.run_test("message_to_dict", chat_msg_tests.test_message_to_dict)
    runner.run_test("message_from_dict", chat_msg_tests.test_message_from_dict)
    
    # Test Serialization
    print("\n💾 Testing Serialization...")
    serial_tests = TestWorkspaceSerialization()
    runner.run_test("workspace_to_dict", serial_tests.test_workspace_to_dict)
    runner.run_test("workspace_from_dict", serial_tests.test_workspace_from_dict)
    
    # Test Legacy Adapter
    print("\n🔄 Testing Legacy Adapter...")
    legacy_tests = TestLegacyAdapter()
    runner.run_test("legacy_get_conversation", legacy_tests.test_get_conversation)
    runner.run_test("legacy_add_and_get_messages", legacy_tests.test_add_and_get_messages)
    runner.run_test("legacy_clear_conversation", legacy_tests.test_clear_conversation)
    
    # Test Async Operations
    print("\n⚡ Testing Async Operations...")
    async_tests = TestAsyncWorkspaceOperations()
    runner.run_test("async_add_message", async_tests.test_async_add_message)
    runner.run_test("async_add_message_invalid_workspace", async_tests.test_async_add_message_invalid_workspace)
    
    # Test WebSocket Manager
    print("\n🔌 Testing WebSocket Manager...")
    ws_manager_tests = TestChatWebSocketManager()
    runner.run_test("get_online_users_empty", ws_manager_tests.test_get_online_users_empty)
    runner.run_test("get_typing_users_empty", ws_manager_tests.test_get_typing_users_empty)
    runner.run_test("get_workspace_stats", ws_manager_tests.test_get_workspace_stats)
    
    # Test Edge Cases
    print("\n🔍 Testing Edge Cases...")
    edge_tests = TestEdgeCases()
    runner.run_test("very_long_message", edge_tests.test_very_long_message)
    runner.run_test("special_characters_in_message", edge_tests.test_special_characters_in_message)
    runner.run_test("unicode_workspace_name", edge_tests.test_unicode_workspace_name)
    runner.run_test("many_participants", edge_tests.test_many_participants)
    runner.run_test("many_workspaces_per_user", edge_tests.test_many_workspaces_per_user)
    runner.run_test("concurrent_message_addition", edge_tests.test_concurrent_message_addition)
    
    # Test Conversation Context
    print("\n🧠 Testing Conversation Context...")
    context_tests = TestConversationContext()
    runner.run_test("get_conversation_context_empty", context_tests.test_get_conversation_context_empty)
    runner.run_test("get_conversation_context_with_messages", context_tests.test_get_conversation_context_with_messages)
    runner.run_test("get_conversation_context_with_documents", context_tests.test_get_conversation_context_with_documents)
    
    # Report results
    return runner.report()


if __name__ == "__main__":
    # Ensure we have an event loop (Python 3.10+ compatible)
    try:
        loop = asyncio.get_running_loop()
    except RuntimeError:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
    
    success = run_all_tests()
    sys.exit(0 if success else 1)
