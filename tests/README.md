# Collaborative Chat System - Test Suite

This directory contains comprehensive test suites for the collaborative chat system.

## Test Files

### 1. `test_collaborative_chat.py` - Unit Tests
**Status:** ✅ All 48 tests passing

Comprehensive unit tests covering:
- Workspace CRUD operations
- Participant management
- Message operations
- Document context management
- ChatMessage serialization
- Workspace serialization
- Legacy adapter compatibility
- Async operations
- WebSocket manager
- Edge cases (long messages, Unicode, concurrency)
- Conversation context building

**Run:**
```bash
# Activate your global Python environment
globalpy

# Run all tests
cd Backend
python tests/test_collaborative_chat.py

# Or with pytest (if installed)
pytest tests/test_collaborative_chat.py -v

# With coverage
pytest tests/test_collaborative_chat.py -v --cov=app.core.workspace_manager --cov=app.core.chat_websocket
```

### 2. `test_collaborative_chat_api.py` - API Integration Tests
**Status:** Ready to run (requires server)

Tests the actual HTTP endpoints and WebSocket connections:
- Workspace API endpoints (CRUD)
- Participant management endpoints
- Message endpoints
- Chat endpoints (with AI responses)
- Document context endpoints
- Presence endpoints
- WebSocket real-time functionality

**Run:**
```bash
# Terminal 1: Start the backend server
cd Backend
globalpy
uvicorn app.main:app --reload --port 8000

# Terminal 2: Run API tests
cd Backend
globalpy
python tests/test_collaborative_chat_api.py

# Or with custom backend URL
BACKEND_URL=http://localhost:8000 python tests/test_collaborative_chat_api.py
```

## Test Coverage

### Unit Tests (48 tests)
- ✅ Workspace Manager (8 tests)
- ✅ Participant Management (6 tests)
- ✅ Message Operations (8 tests)
- ✅ Document Context (5 tests)
- ✅ ChatMessage (2 tests)
- ✅ Serialization (2 tests)
- ✅ Legacy Adapter (3 tests)
- ✅ Async Operations (2 tests)
- ✅ WebSocket Manager (3 tests)
- ✅ Edge Cases (6 tests)
- ✅ Conversation Context (3 tests)

### API Integration Tests
- Workspace CRUD
- Participant Management
- Message Operations
- Chat with AI
- Document Context
- Presence Tracking
- WebSocket Connectivity

## Test Results

### Latest Run
```
============================================================
Test Results: 48/48 passed
============================================================
```

## Troubleshooting

### Import Errors
If you see import errors, make sure:
1. You're in the `Backend` directory
2. Your Python environment has all dependencies installed
3. The `PYTHONPATH` includes the Backend directory

### Server Not Running
For API tests, ensure:
1. The backend server is running on port 8000
2. MongoDB is configured (if using persistence)
3. OpenAI API key is set (for chat tests)

### WebSocket Tests Failing
WebSocket tests require:
1. Server running with WebSocket support
2. Correct WebSocket URL (ws://localhost:8000)
3. Network access enabled

## Adding New Tests

### Unit Test Example
```python
def test_new_feature(self):
    """Test description"""
    # Arrange
    user_id = generate_user_id()
    workspace = self.manager.create_workspace(owner_id=user_id)
    
    # Act
    result = workspace.some_method()
    
    # Assert
    assert result is not None
```

### API Test Example
```python
def test_new_endpoint(self):
    """Test POST /new-endpoint"""
    resp = self.client.post(
        "/new-endpoint",
        data={"key": "value"},
        params={"user_id": self.user_id}
    )
    
    passed = resp.status_code == 200
    self.tracker.record("test_new_endpoint", passed)
```

## Notes

- Tests use unique IDs to avoid conflicts
- Tests clean up after themselves
- API tests require a running server
- Some tests may fail if OpenAI API key is not configured (chat tests)
- WebSocket tests require `websockets` package
