#!/usr/bin/env python3
"""
API Integration Tests for Collaborative Chat System
====================================================

This script tests the actual HTTP endpoints of the collaborative chat system.
Requires the backend server to be running.

Usage:
    # Start the backend server first (in another terminal):
    cd Backend && uvicorn app.main:app --reload --port 8000
    
    # Activate your global Python environment
    globalpy
    
    # Run the tests
    python tests/test_collaborative_chat_api.py
    
    # Or with a custom base URL
    BACKEND_URL=http://localhost:8000 python tests/test_collaborative_chat_api.py
"""

import sys
import os
import asyncio
import time
import uuid
import json
import requests
from typing import Dict, Any, Optional, List
from dataclasses import dataclass
import websockets
from concurrent.futures import ThreadPoolExecutor

# Configuration
BASE_URL = os.environ.get("BACKEND_URL", "http://localhost:8000")
WS_BASE_URL = BASE_URL.replace("http", "ws")
API_KEY = os.environ.get("BACKEND_API_KEY", "")

# Colors for terminal output
class Colors:
    GREEN = "\033[92m"
    RED = "\033[91m"
    YELLOW = "\033[93m"
    BLUE = "\033[94m"
    RESET = "\033[0m"
    BOLD = "\033[1m"


def print_header(text: str):
    """Print a section header"""
    print(f"\n{Colors.BLUE}{Colors.BOLD}{'='*60}")
    print(f"  {text}")
    print(f"{'='*60}{Colors.RESET}\n")


def print_test(name: str, passed: bool, message: str = ""):
    """Print test result"""
    if passed:
        print(f"  {Colors.GREEN}✅ {name}{Colors.RESET}")
    else:
        print(f"  {Colors.RED}❌ {name}: {message}{Colors.RESET}")


def print_info(text: str):
    """Print info message"""
    print(f"  {Colors.YELLOW}ℹ️  {text}{Colors.RESET}")


# ============================================================================
# Test Utilities
# ============================================================================

class APIClient:
    """HTTP client for API tests"""
    
    def __init__(self, base_url: str = BASE_URL):
        self.base_url = base_url.rstrip("/")
        self.headers = {
            "Content-Type": "application/json",
            "X-API-Key": API_KEY
        }
    
    def get(self, path: str, params: Dict = None) -> requests.Response:
        """Make GET request"""
        url = f"{self.base_url}{path}"
        return requests.get(url, params=params, headers=self.headers)
    
    def post(self, path: str, data: Dict = None, params: Dict = None) -> requests.Response:
        """Make POST request"""
        url = f"{self.base_url}{path}"
        return requests.post(url, json=data, params=params, headers=self.headers)
    
    def put(self, path: str, data: Dict = None, params: Dict = None) -> requests.Response:
        """Make PUT request"""
        url = f"{self.base_url}{path}"
        return requests.put(url, json=data, params=params, headers=self.headers)
    
    def delete(self, path: str, params: Dict = None) -> requests.Response:
        """Make DELETE request"""
        url = f"{self.base_url}{path}"
        return requests.delete(url, params=params, headers=self.headers)


def generate_user_id() -> str:
    """Generate a unique user ID"""
    return f"api_test_user_{uuid.uuid4().hex[:8]}"


def generate_workspace_name() -> str:
    """Generate a unique workspace name"""
    return f"API Test Workspace {uuid.uuid4().hex[:6]}"


# ============================================================================
# Test Result Tracking
# ============================================================================

# Import shared TestResult from test_utils
from test_utils import TestResult

class TestTracker:
    def __init__(self):
        self.results: List[TestResult] = []
        self.passed = 0
        self.failed = 0
    
    def record(self, name: str, passed: bool, message: str = "", duration: float = 0):
        self.results.append(TestResult(name, passed, message, duration))
        if passed:
            self.passed += 1
        else:
            self.failed += 1
        print_test(name, passed, message)
    
    def summary(self):
        total = self.passed + self.failed
        print_header(f"Test Summary: {self.passed}/{total} passed")
        if self.failed > 0:
            print(f"{Colors.RED}Failed tests:{Colors.RESET}")
            for r in self.results:
                if not r.passed:
                    print(f"  - {r.name}: {r.message}")
        return self.failed == 0


# ============================================================================
# API Tests
# ============================================================================

class WorkspaceAPITests:
    """Tests for workspace API endpoints"""
    
    def __init__(self, client: APIClient, tracker: TestTracker):
        self.client = client
        self.tracker = tracker
        self.test_user_id = generate_user_id()
        self.created_workspaces: List[str] = []
    
    def cleanup(self):
        """Clean up test workspaces"""
        for ws_id in self.created_workspaces:
            try:
                self.client.delete(
                    f"/workspaces/{ws_id}",
                    params={"user_id": self.test_user_id}
                )
            except:
                pass
    
    def test_create_workspace(self):
        """Test POST /workspaces"""
        name = generate_workspace_name()
        resp = self.client.post(
            "/workspaces",
            data={"name": name},
            params={"user_id": self.test_user_id}
        )
        
        if resp.status_code == 200:
            data = resp.json()
            self.created_workspaces.append(data.get("id", ""))
            passed = (
                data.get("name") == name and
                data.get("owner_id") == self.test_user_id and
                self.test_user_id in data.get("participants", [])
            )
            self.tracker.record("create_workspace", passed, 
                f"Status: {resp.status_code}" if not passed else "")
            return data.get("id")
        else:
            self.tracker.record("create_workspace", False, f"Status: {resp.status_code}")
            return None
    
    def test_create_workspace_with_custom_id(self):
        """Test POST /workspaces with custom workspace_id"""
        custom_id = f"custom_{uuid.uuid4().hex[:12]}"
        resp = self.client.post(
            "/workspaces",
            data={"name": "Custom ID WS", "workspace_id": custom_id},
            params={"user_id": self.test_user_id}
        )
        
        if resp.status_code == 200:
            data = resp.json()
            self.created_workspaces.append(data.get("id", ""))
            passed = data.get("id") == custom_id
            self.tracker.record("create_workspace_custom_id", passed,
                f"Expected {custom_id}, got {data.get('id')}" if not passed else "")
        else:
            self.tracker.record("create_workspace_custom_id", False, f"Status: {resp.status_code}")
    
    def test_list_workspaces(self):
        """Test GET /workspaces"""
        # Create a few workspaces first
        for _ in range(3):
            self.client.post(
                "/workspaces",
                data={"name": generate_workspace_name()},
                params={"user_id": self.test_user_id}
            )
        
        resp = self.client.get("/workspaces", params={"user_id": self.test_user_id})
        
        if resp.status_code == 200:
            data = resp.json()
            passed = isinstance(data, list) and len(data) >= 3
            self.tracker.record("list_workspaces", passed,
                f"Expected at least 3 workspaces, got {len(data)}" if not passed else "")
        else:
            self.tracker.record("list_workspaces", False, f"Status: {resp.status_code}")
    
    def test_get_workspace(self, workspace_id: str):
        """Test GET /workspaces/{workspace_id}"""
        resp = self.client.get(
            f"/workspaces/{workspace_id}",
            params={"user_id": self.test_user_id}
        )
        
        if resp.status_code == 200:
            data = resp.json()
            passed = data.get("id") == workspace_id
            self.tracker.record("get_workspace", passed)
        else:
            self.tracker.record("get_workspace", False, f"Status: {resp.status_code}")
    
    def test_get_workspace_unauthorized(self, workspace_id: str):
        """Test GET /workspaces/{workspace_id} with unauthorized user"""
        other_user = generate_user_id()
        resp = self.client.get(
            f"/workspaces/{workspace_id}",
            params={"user_id": other_user}
        )
        
        # Should return 403 Forbidden
        passed = resp.status_code == 403
        self.tracker.record("get_workspace_unauthorized", passed,
            f"Expected 403, got {resp.status_code}" if not passed else "")
    
    def test_get_nonexistent_workspace(self):
        """Test GET /workspaces/{workspace_id} for nonexistent workspace"""
        resp = self.client.get(
            "/workspaces/nonexistent_workspace_12345",
            params={"user_id": self.test_user_id}
        )
        
        passed = resp.status_code == 404
        self.tracker.record("get_nonexistent_workspace", passed,
            f"Expected 404, got {resp.status_code}" if not passed else "")
    
    def test_delete_workspace(self, workspace_id: str):
        """Test DELETE /workspaces/{workspace_id}"""
        resp = self.client.delete(
            f"/workspaces/{workspace_id}",
            params={"user_id": self.test_user_id}
        )
        
        if resp.status_code == 200:
            # Verify it's deleted
            verify_resp = self.client.get(
                f"/workspaces/{workspace_id}",
                params={"user_id": self.test_user_id}
            )
            passed = verify_resp.status_code == 404
            self.tracker.record("delete_workspace", passed)
            if workspace_id in self.created_workspaces:
                self.created_workspaces.remove(workspace_id)
        else:
            self.tracker.record("delete_workspace", False, f"Status: {resp.status_code}")
    
    def test_delete_workspace_wrong_owner(self, workspace_id: str):
        """Test DELETE /workspaces/{workspace_id} by non-owner"""
        other_user = generate_user_id()
        resp = self.client.delete(
            f"/workspaces/{workspace_id}",
            params={"user_id": other_user}
        )
        
        passed = resp.status_code == 403
        self.tracker.record("delete_workspace_wrong_owner", passed,
            f"Expected 403, got {resp.status_code}" if not passed else "")
    
    def run_all(self):
        """Run all workspace tests"""
        print_header("Workspace CRUD Tests")
        
        # Create workspace and use it for other tests
        ws_id = self.test_create_workspace()
        
        if ws_id:
            self.test_create_workspace_with_custom_id()
            self.test_list_workspaces()
            self.test_get_workspace(ws_id)
            self.test_get_workspace_unauthorized(ws_id)
            self.test_get_nonexistent_workspace()
            self.test_delete_workspace_wrong_owner(ws_id)
            
            # Create another workspace for deletion test
            delete_ws_id = self.test_create_workspace()
            if delete_ws_id:
                self.test_delete_workspace(delete_ws_id)


class ParticipantAPITests:
    """Tests for participant management endpoints"""
    
    def __init__(self, client: APIClient, tracker: TestTracker):
        self.client = client
        self.tracker = tracker
        self.owner_id = generate_user_id()
        self.workspace_id: Optional[str] = None
    
    def setup(self):
        """Create a workspace for testing"""
        resp = self.client.post(
            "/workspaces",
            data={"name": "Participant Test WS"},
            params={"user_id": self.owner_id}
        )
        if resp.status_code == 200:
            self.workspace_id = resp.json().get("id")
    
    def cleanup(self):
        """Clean up test workspace"""
        if self.workspace_id:
            self.client.delete(
                f"/workspaces/{self.workspace_id}",
                params={"user_id": self.owner_id}
            )
    
    def test_add_participant(self):
        """Test POST /workspaces/{id}/participants"""
        participant = generate_user_id()
        resp = self.client.post(
            f"/workspaces/{self.workspace_id}/participants",
            data={"user_id": participant},
            params={"added_by": self.owner_id}
        )
        
        passed = resp.status_code == 200 and resp.json().get("success", False)
        self.tracker.record("add_participant", passed,
            f"Status: {resp.status_code}" if not passed else "")
        return participant
    
    def test_add_participant_unauthorized(self):
        """Test POST /workspaces/{id}/participants by non-participant"""
        outsider = generate_user_id()
        new_user = generate_user_id()
        
        resp = self.client.post(
            f"/workspaces/{self.workspace_id}/participants",
            data={"user_id": new_user},
            params={"added_by": outsider}
        )
        
        passed = resp.status_code == 403
        self.tracker.record("add_participant_unauthorized", passed,
            f"Expected 403, got {resp.status_code}" if not passed else "")
    
    def test_remove_participant(self, participant: str):
        """Test DELETE /workspaces/{id}/participants/{userId}"""
        resp = self.client.delete(
            f"/workspaces/{self.workspace_id}/participants/{participant}",
            params={"removed_by": self.owner_id}
        )
        
        passed = resp.status_code == 200
        self.tracker.record("remove_participant", passed,
            f"Status: {resp.status_code}" if not passed else "")
    
    def run_all(self):
        """Run all participant tests"""
        print_header("Participant Management Tests")
        
        self.setup()
        if self.workspace_id:
            participant = self.test_add_participant()
            self.test_add_participant_unauthorized()
            if participant:
                self.test_remove_participant(participant)
        else:
            print_info("Skipping tests - workspace creation failed")


class MessageAPITests:
    """Tests for message endpoints"""
    
    def __init__(self, client: APIClient, tracker: TestTracker):
        self.client = client
        self.tracker = tracker
        self.user_id = generate_user_id()
        self.workspace_id: Optional[str] = None
    
    def setup(self):
        """Create a workspace for testing"""
        resp = self.client.post(
            "/workspaces",
            data={"name": "Message Test WS"},
            params={"user_id": self.user_id}
        )
        if resp.status_code == 200:
            self.workspace_id = resp.json().get("id")
    
    def cleanup(self):
        """Clean up test workspace"""
        if self.workspace_id:
            self.client.delete(
                f"/workspaces/{self.workspace_id}",
                params={"user_id": self.user_id}
            )
    
    def test_send_message(self):
        """Test POST /workspaces/{id}/messages"""
        resp = self.client.post(
            f"/workspaces/{self.workspace_id}/messages",
            data={"content": "Hello, API test!", "metadata": {"test": True}},
            params={"user_id": self.user_id}
        )
        
        if resp.status_code == 200:
            data = resp.json()
            passed = (
                data.get("content") == "Hello, API test!" and
                data.get("sender_id") == self.user_id
            )
            self.tracker.record("send_message", passed)
        else:
            self.tracker.record("send_message", False, f"Status: {resp.status_code}")
    
    def test_send_empty_message(self):
        """Test POST /workspaces/{id}/messages with empty content"""
        resp = self.client.post(
            f"/workspaces/{self.workspace_id}/messages",
            data={"content": ""},
            params={"user_id": self.user_id}
        )
        
        passed = resp.status_code == 400
        self.tracker.record("send_empty_message_rejected", passed,
            f"Expected 400, got {resp.status_code}" if not passed else "")
    
    def test_get_messages(self):
        """Test GET /workspaces/{id}/messages"""
        # Send a few messages first
        for i in range(3):
            self.client.post(
                f"/workspaces/{self.workspace_id}/messages",
                data={"content": f"Message {i}"},
                params={"user_id": self.user_id}
            )
        
        resp = self.client.get(
            f"/workspaces/{self.workspace_id}/messages",
            params={"user_id": self.user_id}
        )
        
        if resp.status_code == 200:
            data = resp.json()
            passed = isinstance(data, list) and len(data) >= 3
            self.tracker.record("get_messages", passed,
                f"Expected at least 3 messages, got {len(data)}" if not passed else "")
        else:
            self.tracker.record("get_messages", False, f"Status: {resp.status_code}")
    
    def test_get_messages_with_limit(self):
        """Test GET /workspaces/{id}/messages with limit"""
        resp = self.client.get(
            f"/workspaces/{self.workspace_id}/messages",
            params={"user_id": self.user_id, "limit": 2}
        )
        
        if resp.status_code == 200:
            data = resp.json()
            passed = len(data) <= 2
            self.tracker.record("get_messages_with_limit", passed,
                f"Expected max 2 messages, got {len(data)}" if not passed else "")
        else:
            self.tracker.record("get_messages_with_limit", False, f"Status: {resp.status_code}")
    
    def test_clear_messages(self):
        """Test POST /workspaces/{id}/clear"""
        resp = self.client.post(
            f"/workspaces/{self.workspace_id}/clear",
            params={"user_id": self.user_id}
        )
        
        passed = resp.status_code == 200
        self.tracker.record("clear_messages", passed,
            f"Status: {resp.status_code}" if not passed else "")
    
    def run_all(self):
        """Run all message tests"""
        print_header("Message Tests")
        
        self.setup()
        if self.workspace_id:
            self.test_send_message()
            self.test_send_empty_message()
            self.test_get_messages()
            self.test_get_messages_with_limit()
            self.test_clear_messages()
        else:
            print_info("Skipping tests - workspace creation failed")


class ChatAPITests:
    """Tests for chat (with AI response) endpoints"""
    
    def __init__(self, client: APIClient, tracker: TestTracker):
        self.client = client
        self.tracker = tracker
        self.user_id = generate_user_id()
        self.workspace_id: Optional[str] = None
    
    def setup(self):
        """Create a workspace for testing"""
        resp = self.client.post(
            "/workspaces",
            data={"name": "Chat Test WS"},
            params={"user_id": self.user_id}
        )
        if resp.status_code == 200:
            self.workspace_id = resp.json().get("id")
    
    def cleanup(self):
        """Clean up test workspace"""
        if self.workspace_id:
            self.client.delete(
                f"/workspaces/{self.workspace_id}",
                params={"user_id": self.user_id}
            )
    
    def test_chat_basic(self):
        """Test POST /workspaces/{id}/chat"""
        resp = self.client.post(
            f"/workspaces/{self.workspace_id}/chat",
            data={"message": "Hello! What can you help me with?"},
            params={"user_id": self.user_id}
        )
        
        if resp.status_code == 200:
            data = resp.json()
            passed = (
                data.get("success", False) and
                data.get("reply") is not None and
                len(data.get("reply", "")) > 0
            )
            self.tracker.record("chat_basic", passed,
                f"No reply received" if not passed else "")
        else:
            # May fail if no OpenAI key configured
            self.tracker.record("chat_basic", False, 
                f"Status: {resp.status_code} (check OPENAI_API_KEY)")
    
    def test_chat_with_schema(self):
        """Test POST /workspaces/{id}/chat with schema levels"""
        resp = self.client.post(
            f"/workspaces/{self.workspace_id}/chat",
            data={
                "message": "What are the current schema settings?",
                "schemaLevels": {"anti_scanner_techniques": 3, "entropy_management": 2}
            },
            params={"user_id": self.user_id}
        )
        
        if resp.status_code == 200:
            data = resp.json()
            passed = data.get("success", False)
            self.tracker.record("chat_with_schema", passed)
        else:
            self.tracker.record("chat_with_schema", False, f"Status: {resp.status_code}")
    
    def test_chat_empty_message(self):
        """Test POST /workspaces/{id}/chat with empty message"""
        resp = self.client.post(
            f"/workspaces/{self.workspace_id}/chat",
            data={"message": ""},
            params={"user_id": self.user_id}
        )
        
        passed = resp.status_code == 400
        self.tracker.record("chat_empty_message_rejected", passed,
            f"Expected 400, got {resp.status_code}" if not passed else "")
    
    def test_chat_long_message(self):
        """Test POST /workspaces/{id}/chat with long message"""
        long_message = "Hello! " * 500  # ~3500 chars
        resp = self.client.post(
            f"/workspaces/{self.workspace_id}/chat",
            data={"message": long_message},
            params={"user_id": self.user_id}
        )
        
        # Should succeed (under 10000 char limit)
        passed = resp.status_code == 200
        self.tracker.record("chat_long_message", passed,
            f"Status: {resp.status_code}" if not passed else "")
    
    def test_chat_unauthorized(self):
        """Test POST /workspaces/{id}/chat by non-participant"""
        other_user = generate_user_id()
        resp = self.client.post(
            f"/workspaces/{self.workspace_id}/chat",
            data={"message": "Hello from outsider"},
            params={"user_id": other_user}
        )
        
        passed = resp.status_code == 403
        self.tracker.record("chat_unauthorized", passed,
            f"Expected 403, got {resp.status_code}" if not passed else "")
    
    def run_all(self):
        """Run all chat tests"""
        print_header("Chat (AI) Tests")
        
        self.setup()
        if self.workspace_id:
            self.test_chat_basic()
            self.test_chat_with_schema()
            self.test_chat_empty_message()
            self.test_chat_long_message()
            self.test_chat_unauthorized()
        else:
            print_info("Skipping tests - workspace creation failed")


class DocumentAPITests:
    """Tests for document context endpoints"""
    
    def __init__(self, client: APIClient, tracker: TestTracker):
        self.client = client
        self.tracker = tracker
        self.user_id = generate_user_id()
        self.workspace_id: Optional[str] = None
    
    def setup(self):
        """Create a workspace for testing"""
        resp = self.client.post(
            "/workspaces",
            data={"name": "Document Test WS"},
            params={"user_id": self.user_id}
        )
        if resp.status_code == 200:
            self.workspace_id = resp.json().get("id")
    
    def cleanup(self):
        """Clean up test workspace"""
        if self.workspace_id:
            self.client.delete(
                f"/workspaces/{self.workspace_id}",
                params={"user_id": self.user_id}
            )
    
    def test_add_document(self):
        """Test POST /workspaces/{id}/documents"""
        resp = self.client.post(
            f"/workspaces/{self.workspace_id}/documents",
            data={
                "file_id": "test_file_123",
                "filename": "test_document.docx",
                "file_type": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                "job_id": "job_456"
            },
            params={"user_id": self.user_id}
        )
        
        passed = resp.status_code == 200 and resp.json().get("success", False)
        self.tracker.record("add_document", passed,
            f"Status: {resp.status_code}" if not passed else "")
    
    def test_get_documents(self):
        """Test GET /workspaces/{id}/documents"""
        # Add a document first
        self.client.post(
            f"/workspaces/{self.workspace_id}/documents",
            data={
                "file_id": "file_for_get_test",
                "filename": "get_test.pdf",
                "file_type": "application/pdf"
            },
            params={"user_id": self.user_id}
        )
        
        resp = self.client.get(
            f"/workspaces/{self.workspace_id}/documents",
            params={"user_id": self.user_id}
        )
        
        if resp.status_code == 200:
            data = resp.json()
            passed = (
                "documents" in data and
                len(data["documents"]) >= 1
            )
            self.tracker.record("get_documents", passed)
        else:
            self.tracker.record("get_documents", False, f"Status: {resp.status_code}")
    
    def test_set_active_document(self):
        """Test PUT /workspaces/{id}/documents/{fileId}/active"""
        # Add multiple documents
        self.client.post(
            f"/workspaces/{self.workspace_id}/documents",
            data={"file_id": "active_test_1", "filename": "doc1.docx", "file_type": "docx"},
            params={"user_id": self.user_id}
        )
        self.client.post(
            f"/workspaces/{self.workspace_id}/documents",
            data={"file_id": "active_test_2", "filename": "doc2.docx", "file_type": "docx"},
            params={"user_id": self.user_id}
        )
        
        resp = self.client.put(
            f"/workspaces/{self.workspace_id}/documents/active_test_2/active",
            params={"user_id": self.user_id}
        )
        
        passed = resp.status_code == 200 and resp.json().get("success", False)
        self.tracker.record("set_active_document", passed,
            f"Status: {resp.status_code}" if not passed else "")
    
    def test_set_active_nonexistent_document(self):
        """Test PUT /workspaces/{id}/documents/{fileId}/active for nonexistent document"""
        resp = self.client.put(
            f"/workspaces/{self.workspace_id}/documents/nonexistent_file/active",
            params={"user_id": self.user_id}
        )
        
        passed = resp.status_code == 404
        self.tracker.record("set_active_nonexistent_document", passed,
            f"Expected 404, got {resp.status_code}" if not passed else "")
    
    def run_all(self):
        """Run all document tests"""
        print_header("Document Context Tests")
        
        self.setup()
        if self.workspace_id:
            self.test_add_document()
            self.test_get_documents()
            self.test_set_active_document()
            self.test_set_active_nonexistent_document()
        else:
            print_info("Skipping tests - workspace creation failed")


class WebSocketTests:
    """Tests for WebSocket connectivity"""
    
    def __init__(self, client: APIClient, tracker: TestTracker):
        self.client = client
        self.tracker = tracker
        self.user_id = generate_user_id()
        self.workspace_id: Optional[str] = None
    
    def setup(self):
        """Create a workspace for testing"""
        resp = self.client.post(
            "/workspaces",
            data={"name": "WebSocket Test WS"},
            params={"user_id": self.user_id}
        )
        if resp.status_code == 200:
            self.workspace_id = resp.json().get("id")
    
    def cleanup(self):
        """Clean up test workspace"""
        if self.workspace_id:
            self.client.delete(
                f"/workspaces/{self.workspace_id}",
                params={"user_id": self.user_id}
            )
    
    async def test_websocket_connection(self):
        """Test WebSocket connection"""
        uri = f"{WS_BASE_URL}/workspaces/{self.workspace_id}/ws?user_id={self.user_id}"
        
        try:
            async with websockets.connect(uri, close_timeout=5) as ws:
                # Send ping
                await ws.send(json.dumps({"type": "ping"}))
                
                # Wait for response
                try:
                    response = await asyncio.wait_for(ws.recv(), timeout=5)
                    data = json.loads(response)
                    
                    # Should receive either pong or presence update
                    passed = data.get("type") in ["pong", "presence", "direct"]
                    self.tracker.record("websocket_connection", passed,
                        f"Unexpected response type: {data.get('type')}" if not passed else "")
                except asyncio.TimeoutError:
                    self.tracker.record("websocket_connection", False, "Timeout waiting for response")
        except Exception as e:
            self.tracker.record("websocket_connection", False, f"Connection failed: {e}")
    
    async def test_websocket_typing_indicator(self):
        """Test WebSocket typing indicator"""
        uri = f"{WS_BASE_URL}/workspaces/{self.workspace_id}/ws?user_id={self.user_id}"
        
        try:
            async with websockets.connect(uri, close_timeout=5) as ws:
                # Send typing indicator
                await ws.send(json.dumps({
                    "type": "typing",
                    "data": {"is_typing": True}
                }))
                
                # Small delay to process
                await asyncio.sleep(0.5)
                
                self.tracker.record("websocket_typing_indicator", True)
        except Exception as e:
            self.tracker.record("websocket_typing_indicator", False, f"Error: {e}")
    
    async def test_websocket_unauthorized(self):
        """Test WebSocket connection with unauthorized user"""
        other_user = generate_user_id()
        uri = f"{WS_BASE_URL}/workspaces/{self.workspace_id}/ws?user_id={other_user}"
        
        try:
            async with websockets.connect(uri, close_timeout=5) as ws:
                # Should be rejected immediately
                try:
                    await asyncio.wait_for(ws.recv(), timeout=2)
                    self.tracker.record("websocket_unauthorized", False, 
                        "Connection should have been rejected")
                except websockets.exceptions.ConnectionClosed as e:
                    passed = e.code == 4003  # Our custom unauthorized code
                    self.tracker.record("websocket_unauthorized", passed,
                        f"Expected close code 4003, got {e.code}" if not passed else "")
        except Exception as e:
            # Check if the error message indicates HTTP 403 rejection
            # This is the expected behavior - server should reject unauthorized connections
            error_str = str(e)
            error_type = type(e).__name__
            
            # Check for various indicators of 403 rejection
            is_403_rejection = (
                '403' in error_str or 
                'HTTP 403' in error_str or 
                'Forbidden' in error_str or
                'rejected' in error_str.lower() and '403' in error_str
            )
            
            # Also check if it's a websockets exception that indicates rejection
            if isinstance(e, (websockets.exceptions.InvalidStatusCode,
                             websockets.exceptions.InvalidHandshake)):
                status_code = getattr(e, 'status_code', None)
                if status_code == 403:
                    is_403_rejection = True
            
            if is_403_rejection:
                # This is actually the expected behavior - server rejected with 403
                self.tracker.record("websocket_unauthorized", True, "")
            elif isinstance(e, websockets.exceptions.ConnectionClosed):
                # Check for close code 4003
                passed = e.code == 4003
                self.tracker.record("websocket_unauthorized", passed,
                    f"Expected close code 4003, got {e.code}" if not passed else "")
            else:
                self.tracker.record("websocket_unauthorized", False, 
                    f"Unexpected error ({error_type}): {e}")
    
    def run_all(self):
        """Run all WebSocket tests"""
        print_header("WebSocket Tests")
        
        self.setup()
        if self.workspace_id:
            # Use new_event_loop() to avoid deprecation warning (Python 3.10+)
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            try:
                loop.run_until_complete(self.test_websocket_connection())
                loop.run_until_complete(self.test_websocket_typing_indicator())
                loop.run_until_complete(self.test_websocket_unauthorized())
            finally:
                loop.close()
        else:
            print_info("Skipping tests - workspace creation failed")


class PresenceAPITests:
    """Tests for presence endpoint"""
    
    def __init__(self, client: APIClient, tracker: TestTracker):
        self.client = client
        self.tracker = tracker
        self.user_id = generate_user_id()
        self.workspace_id: Optional[str] = None
    
    def setup(self):
        """Create a workspace for testing"""
        resp = self.client.post(
            "/workspaces",
            data={"name": "Presence Test WS"},
            params={"user_id": self.user_id}
        )
        if resp.status_code == 200:
            self.workspace_id = resp.json().get("id")
    
    def cleanup(self):
        """Clean up test workspace"""
        if self.workspace_id:
            self.client.delete(
                f"/workspaces/{self.workspace_id}",
                params={"user_id": self.user_id}
            )
    
    def test_get_presence(self):
        """Test GET /workspaces/{id}/presence"""
        resp = self.client.get(
            f"/workspaces/{self.workspace_id}/presence",
            params={"user_id": self.user_id}
        )
        
        if resp.status_code == 200:
            data = resp.json()
            passed = (
                "online_count" in data and
                "online_users" in data and
                "typing_users" in data
            )
            self.tracker.record("get_presence", passed)
        else:
            self.tracker.record("get_presence", False, f"Status: {resp.status_code}")
    
    def run_all(self):
        """Run all presence tests"""
        print_header("Presence Tests")
        
        self.setup()
        if self.workspace_id:
            self.test_get_presence()
        else:
            print_info("Skipping tests - workspace creation failed")


# ============================================================================
# Main Test Runner
# ============================================================================

def check_server_health(client: APIClient) -> bool:
    """Check if the server is running and healthy"""
    try:
        resp = client.get("/health/fast")
        return resp.status_code == 200
    except requests.exceptions.ConnectionError:
        return False


def run_all_tests():
    """Run all API tests"""
    print(f"\n{Colors.BOLD}{'='*60}")
    print("Collaborative Chat API Integration Tests")
    print(f"Base URL: {BASE_URL}")
    print(f"{'='*60}{Colors.RESET}\n")
    
    client = APIClient()
    tracker = TestTracker()
    
    # Check server health first
    print_info("Checking server health...")
    if not check_server_health(client):
        print(f"\n{Colors.RED}❌ Server is not running at {BASE_URL}")
        print(f"   Please start the server first:{Colors.RESET}")
        print(f"   cd Backend && uvicorn app.main:app --reload --port 8000\n")
        return False
    print(f"  {Colors.GREEN}✓ Server is running{Colors.RESET}\n")
    
    # Run all test suites
    test_suites = [
        WorkspaceAPITests(client, tracker),
        ParticipantAPITests(client, tracker),
        MessageAPITests(client, tracker),
        ChatAPITests(client, tracker),
        DocumentAPITests(client, tracker),
        PresenceAPITests(client, tracker),
        WebSocketTests(client, tracker),
    ]
    
    for suite in test_suites:
        try:
            suite.run_all()
        except Exception as e:
            print(f"  {Colors.RED}Error in test suite: {e}{Colors.RESET}")
        finally:
            if hasattr(suite, 'cleanup'):
                suite.cleanup()
    
    # Print summary
    return tracker.summary()


if __name__ == "__main__":
    success = run_all_tests()
    sys.exit(0 if success else 1)
