"""
Workspace & Collaborative Chat API Routes
Handles workspace management, collaborative conversations, and real-time chat.
"""
from fastapi import APIRouter, HTTPException, WebSocket, WebSocketDisconnect, Query, Depends
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any
import asyncio

from app.core.workspace_manager import workspace_manager, Workspace, ChatMessage
from app.core.chat_websocket import chat_ws_manager
from app.core.dependencies import get_settings
from app.core.logger import get_logger

logger = get_logger('workspace')

router = APIRouter(prefix="/workspaces", tags=["workspaces"])


# ============================================================================
# Request/Response Models
# ============================================================================

class CreateWorkspaceRequest(BaseModel):
    name: Optional[str] = None
    workspace_id: Optional[str] = None


class AddParticipantRequest(BaseModel):
    user_id: str


class SendMessageRequest(BaseModel):
    content: str
    metadata: Optional[Dict[str, Any]] = None


class WorkspaceChatRequest(BaseModel):
    """Chat request for workspace collaborative chat."""
    message: str
    schema_levels: Optional[Dict[str, int]] = Field(default=None, alias="schemaLevels")
    
    class Config:
        populate_by_name = True


class AddDocumentRequest(BaseModel):
    file_id: str
    filename: str
    file_type: str
    job_id: Optional[str] = None


class WorkspaceResponse(BaseModel):
    id: str
    name: str
    owner_id: str
    participants: List[str]
    message_count: int
    document_count: int
    active_document_id: Optional[str]
    created_at: float
    updated_at: float


class MessageResponse(BaseModel):
    id: str
    conversation_id: str
    sender_id: str
    role: str
    content: str
    timestamp: float
    metadata: Dict[str, Any] = {}


def workspace_to_response(workspace: Workspace) -> WorkspaceResponse:
    """Convert Workspace to API response"""
    return WorkspaceResponse(
        id=workspace.id,
        name=workspace.name,
        owner_id=workspace.owner_id,
        participants=list(workspace.participants),
        message_count=len(workspace.messages),
        document_count=len(workspace.documents),
        active_document_id=workspace.active_document_id,
        created_at=workspace.created_at,
        updated_at=workspace.updated_at
    )


def message_to_response(message: ChatMessage) -> MessageResponse:
    """Convert ChatMessage to API response"""
    return MessageResponse(
        id=message.id,
        conversation_id=message.conversation_id,
        sender_id=message.sender_id,
        role=message.role,
        content=message.content,
        timestamp=message.timestamp,
        metadata=message.metadata
    )


# ============================================================================
# Workspace Management Endpoints
# ============================================================================

@router.post("", response_model=WorkspaceResponse)
async def create_workspace(
    request: CreateWorkspaceRequest,
    user_id: str = Query(..., description="User ID creating the workspace")
):
    """Create a new workspace"""
    try:
        workspace = workspace_manager.create_workspace(
            owner_id=user_id,
            name=request.name,
            workspace_id=request.workspace_id
        )
        
        # Add a welcome system message
        workspace.add_message(
            sender_id="system",
            role="system",
            content="Welcome to this collaborative workspace! I'm your AI assistant. "
                    "I can help you refine documents, answer questions, and collaborate with your team. "
                    "Upload a document or ask me anything to get started."
        )
        
        logger.info(f"Workspace created: {workspace.id} by user {user_id}")
        return workspace_to_response(workspace)
    
    except Exception as e:
        logger.error(f"Failed to create workspace: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("", response_model=List[WorkspaceResponse])
async def list_workspaces(
    user_id: str = Query(..., description="User ID to list workspaces for")
):
    """List all workspaces for a user"""
    try:
        workspaces = workspace_manager.get_user_workspaces(user_id)
        return [workspace_to_response(ws) for ws in workspaces]
    
    except Exception as e:
        logger.error(f"Failed to list workspaces: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/{workspace_id}", response_model=WorkspaceResponse)
async def get_workspace(
    workspace_id: str,
    user_id: str = Query(..., description="User ID requesting the workspace")
):
    """Get workspace details"""
    workspace = workspace_manager.get_workspace(workspace_id)
    
    if not workspace:
        raise HTTPException(status_code=404, detail="Workspace not found")
    
    if not workspace.is_participant(user_id):
        raise HTTPException(status_code=403, detail="Not authorized to access this workspace")
    
    return workspace_to_response(workspace)


@router.delete("/{workspace_id}")
async def delete_workspace(
    workspace_id: str,
    user_id: str = Query(..., description="User ID deleting the workspace")
):
    """Delete a workspace (owner only)"""
    workspace = workspace_manager.get_workspace(workspace_id)
    
    if not workspace:
        raise HTTPException(status_code=404, detail="Workspace not found")
    
    if workspace.owner_id != user_id:
        raise HTTPException(status_code=403, detail="Only the workspace owner can delete it")
    
    if workspace_manager.delete_workspace(workspace_id, user_id):
        return {"success": True, "message": "Workspace deleted"}
    
    raise HTTPException(status_code=500, detail="Failed to delete workspace")


# ============================================================================
# Participant Management
# ============================================================================

@router.post("/{workspace_id}/participants")
async def add_participant(
    workspace_id: str,
    request: AddParticipantRequest,
    added_by: str = Query(..., description="User ID adding the participant")
):
    """Add a participant to a workspace"""
    workspace = workspace_manager.get_workspace(workspace_id)
    
    if not workspace:
        raise HTTPException(status_code=404, detail="Workspace not found")
    
    if not workspace.is_participant(added_by):
        raise HTTPException(status_code=403, detail="Not authorized to add participants")
    
    if workspace_manager.add_participant(workspace_id, request.user_id, added_by):
        # Notify via WebSocket
        await chat_ws_manager.broadcast_presence_update(
            workspace_id, 
            request.user_id, 
            "added"
        )
        return {"success": True, "message": f"User {request.user_id} added to workspace"}
    
    return {"success": False, "message": "User is already a participant"}


@router.delete("/{workspace_id}/participants/{target_user_id}")
async def remove_participant(
    workspace_id: str,
    target_user_id: str,
    removed_by: str = Query(..., description="User ID removing the participant")
):
    """Remove a participant from a workspace"""
    workspace = workspace_manager.get_workspace(workspace_id)
    
    if not workspace:
        raise HTTPException(status_code=404, detail="Workspace not found")
    
    # Only owner can remove participants, or user can remove themselves
    if removed_by != workspace.owner_id and removed_by != target_user_id:
        raise HTTPException(status_code=403, detail="Not authorized to remove participants")
    
    if workspace.remove_participant(target_user_id):
        await chat_ws_manager.broadcast_presence_update(
            workspace_id,
            target_user_id,
            "removed"
        )
        return {"success": True, "message": f"User {target_user_id} removed from workspace"}
    
    return {"success": False, "message": "Cannot remove the workspace owner"}


# ============================================================================
# Messages & Chat
# ============================================================================

@router.get("/{workspace_id}/messages", response_model=List[MessageResponse])
async def get_messages(
    workspace_id: str,
    user_id: str = Query(..., description="User ID requesting messages"),
    limit: Optional[int] = Query(None, description="Maximum number of messages to return")
):
    """Get messages from a workspace"""
    workspace = workspace_manager.get_workspace(workspace_id)
    
    if not workspace:
        raise HTTPException(status_code=404, detail="Workspace not found")
    
    if not workspace.is_participant(user_id):
        raise HTTPException(status_code=403, detail="Not authorized to access this workspace")
    
    messages = workspace.get_messages(limit)
    return [message_to_response(msg) for msg in messages]


@router.post("/{workspace_id}/messages", response_model=MessageResponse)
async def send_message(
    workspace_id: str,
    request: SendMessageRequest,
    user_id: str = Query(..., description="User ID sending the message")
):
    """Send a message to a workspace"""
    workspace = workspace_manager.get_workspace(workspace_id)
    
    if not workspace:
        raise HTTPException(status_code=404, detail="Workspace not found")
    
    if not workspace.is_participant(user_id):
        raise HTTPException(status_code=403, detail="Not authorized to send messages to this workspace")
    
    if not request.content.strip():
        raise HTTPException(status_code=400, detail="Message content cannot be empty")
    
    # Add the message
    message = await workspace_manager.add_message(
        workspace_id=workspace_id,
        sender_id=user_id,
        role="user",
        content=request.content,
        metadata=request.metadata
    )
    
    if not message:
        raise HTTPException(status_code=500, detail="Failed to add message")
    
    # Broadcast to other participants via WebSocket
    await chat_ws_manager.broadcast_message(
        workspace_id,
        message.to_dict(),
        exclude_user=user_id
    )
    
    return message_to_response(message)


@router.post("/{workspace_id}/chat")
async def workspace_chat(
    workspace_id: str,
    request: WorkspaceChatRequest,
    user_id: str = Query(..., description="User ID sending the chat")
):
    """
    Send a chat message and get an AI response.
    This is the main collaborative chat endpoint that:
    1. Adds the user message to the workspace
    2. Generates an AI response using conversation context
    3. Broadcasts updates to all participants
    """
    workspace = workspace_manager.get_workspace(workspace_id)
    
    if not workspace:
        raise HTTPException(status_code=404, detail="Workspace not found")
    
    if not workspace.is_participant(user_id):
        raise HTTPException(status_code=403, detail="Not authorized to chat in this workspace")
    
    if not request.message.strip():
        raise HTTPException(status_code=400, detail="Message cannot be empty")
    
    if len(request.message) > 10000:
        raise HTTPException(status_code=400, detail="Message too long. Maximum 10,000 characters")
    
    # Add user message
    user_message = await workspace_manager.add_message(
        workspace_id=workspace_id,
        sender_id=user_id,
        role="user",
        content=request.message,
        metadata={"schema_levels": request.schema_levels} if request.schema_levels else None
    )
    
    # Broadcast user message
    await chat_ws_manager.broadcast_message(
        workspace_id,
        user_message.to_dict(),
        exclude_user=user_id
    )
    
    # Get conversation context
    context = workspace_manager.get_conversation_context(
        workspace_id,
        num_messages=15,
        include_document_context=True
    )
    
    # Generate AI response
    try:
        settings = get_settings()
        api_key = settings.openai_api_key
        
        if not api_key:
            raise HTTPException(status_code=500, detail="OPENAI_API_KEY not configured")
        
        from openai import OpenAI
        client = OpenAI(api_key=api_key)
        
        # Build system prompt for collaborative context
        system_prompt = """You are a collaborative AI assistant helping users refine and improve their documents.

Your capabilities:
- Analyze document content and provide suggestions
- Answer questions about text refinement, formatting, and style
- Help multiple users collaborate on document improvements
- Provide specific, actionable feedback

Guidelines:
- Be conversational and helpful
- Reference specific parts of documents when relevant
- Support team collaboration by acknowledging different perspectives
- Keep responses focused but comprehensive
- When asked to make changes, explain what you're doing and why

You have access to the workspace context including any uploaded documents and the conversation history."""
        
        # Prepare messages for OpenAI
        messages = [{"role": "system", "content": system_prompt}]
        messages.extend(context)
        
        # Call OpenAI
        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=messages,
            max_tokens=2000,
            temperature=0.7
        )
        
        assistant_content = response.choices[0].message.content or "I apologize, I couldn't generate a response."
        
        # Add assistant response to workspace
        assistant_message = await workspace_manager.add_message(
            workspace_id=workspace_id,
            sender_id="assistant",
            role="assistant",
            content=assistant_content
        )
        
        # Broadcast assistant response
        await chat_ws_manager.broadcast_message(
            workspace_id,
            assistant_message.to_dict()
        )
        
        return {
            "success": True,
            "user_message": message_to_response(user_message),
            "assistant_message": message_to_response(assistant_message),
            "reply": assistant_content  # For backward compatibility
        }
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Chat error in workspace {workspace_id}: {e}")
        
        # Add error message
        error_message = await workspace_manager.add_message(
            workspace_id=workspace_id,
            sender_id="system",
            role="assistant",
            content=f"I encountered an error processing your request. Please try again."
        )
        
        return {
            "success": False,
            "error": str(e),
            "user_message": message_to_response(user_message),
            "reply": "I encountered an error. Please try again."
        }


@router.post("/{workspace_id}/clear")
async def clear_workspace_messages(
    workspace_id: str,
    user_id: str = Query(..., description="User ID clearing the messages")
):
    """Clear all messages in a workspace (keeps system messages)"""
    workspace = workspace_manager.get_workspace(workspace_id)
    
    if not workspace:
        raise HTTPException(status_code=404, detail="Workspace not found")
    
    if not workspace.is_participant(user_id):
        raise HTTPException(status_code=403, detail="Not authorized")
    
    workspace.clear_messages()
    
    # Notify participants
    await chat_ws_manager.broadcast_message(
        workspace_id,
        {"type": "messages_cleared", "cleared_by": user_id}
    )
    
    return {"success": True, "message": "Messages cleared"}


# ============================================================================
# Document Context Management
# ============================================================================

@router.post("/{workspace_id}/documents")
async def add_document_to_workspace(
    workspace_id: str,
    request: AddDocumentRequest,
    user_id: str = Query(..., description="User ID adding the document")
):
    """Add a document to the workspace context"""
    workspace = workspace_manager.get_workspace(workspace_id)
    
    if not workspace:
        raise HTTPException(status_code=404, detail="Workspace not found")
    
    if not workspace.is_participant(user_id):
        raise HTTPException(status_code=403, detail="Not authorized")
    
    doc = workspace.add_document(
        file_id=request.file_id,
        filename=request.filename,
        file_type=request.file_type,
        job_id=request.job_id
    )
    
    # Broadcast document added
    await chat_ws_manager.broadcast_document_update(
        workspace_id,
        request.file_id,
        "added",
        {"filename": request.filename, "file_type": request.file_type}
    )
    
    # Add system message
    await workspace_manager.add_message(
        workspace_id=workspace_id,
        sender_id="system",
        role="system",
        content=f"📄 Document added: {request.filename}"
    )
    
    return {"success": True, "document": doc.to_dict()}


@router.put("/{workspace_id}/documents/{file_id}/active")
async def set_active_document(
    workspace_id: str,
    file_id: str,
    user_id: str = Query(..., description="User ID setting the active document")
):
    """Set the active document in the workspace"""
    workspace = workspace_manager.get_workspace(workspace_id)
    
    if not workspace:
        raise HTTPException(status_code=404, detail="Workspace not found")
    
    if not workspace.is_participant(user_id):
        raise HTTPException(status_code=403, detail="Not authorized")
    
    if workspace.set_active_document(file_id):
        # Broadcast active document changed
        await chat_ws_manager.broadcast_document_update(
            workspace_id,
            file_id,
            "active_changed",
            {"set_by": user_id}
        )
        return {"success": True, "active_document_id": file_id}
    
    raise HTTPException(status_code=404, detail="Document not found in workspace")


@router.get("/{workspace_id}/documents")
async def get_workspace_documents(
    workspace_id: str,
    user_id: str = Query(..., description="User ID requesting documents")
):
    """Get all documents in a workspace"""
    workspace = workspace_manager.get_workspace(workspace_id)
    
    if not workspace:
        raise HTTPException(status_code=404, detail="Workspace not found")
    
    if not workspace.is_participant(user_id):
        raise HTTPException(status_code=403, detail="Not authorized")
    
    return {
        "documents": [doc.to_dict() for doc in workspace.documents.values()],
        "active_document_id": workspace.active_document_id
    }


# ============================================================================
# Presence & Real-time
# ============================================================================

@router.get("/{workspace_id}/presence")
async def get_workspace_presence(
    workspace_id: str,
    user_id: str = Query(..., description="User ID requesting presence info")
):
    """Get current presence information for a workspace"""
    workspace = workspace_manager.get_workspace(workspace_id)
    
    if not workspace:
        raise HTTPException(status_code=404, detail="Workspace not found")
    
    if not workspace.is_participant(user_id):
        raise HTTPException(status_code=403, detail="Not authorized")
    
    return chat_ws_manager.get_workspace_stats(workspace_id)


# ============================================================================
# WebSocket Endpoint for Real-time Chat
# ============================================================================

@router.websocket("/{workspace_id}/ws")
async def workspace_websocket(
    websocket: WebSocket,
    workspace_id: str,
    user_id: str = Query(..., description="User ID connecting")
):
    """
    WebSocket endpoint for real-time collaboration.
    
    Message types (client -> server):
    - {"type": "typing", "data": {"is_typing": true/false}}
    - {"type": "ping"}
    - {"type": "request_presence"}
    
    Message types (server -> client):
    - {"type": "message", "data": {...message...}}
    - {"type": "typing", "data": {"user_id": "...", "is_typing": true/false}}
    - {"type": "presence", "data": {"user_id": "...", "status": "joined/left", "online_users": [...]}}
    - {"type": "document_update", "data": {...}}
    - {"type": "pong"}
    """
    # Verify workspace exists and user has access
    workspace = workspace_manager.get_workspace(workspace_id)
    
    if not workspace:
        await websocket.close(code=4004, reason="Workspace not found")
        return
    
    if not workspace.is_participant(user_id):
        await websocket.close(code=4003, reason="Not authorized")
        return
    
    # Connect
    presence = await chat_ws_manager.connect(workspace_id, user_id, websocket)
    
    try:
        while True:
            # Receive message
            data = await websocket.receive_json()
            
            # Handle the message
            await chat_ws_manager.handle_client_message(workspace_id, user_id, data)
    
    except WebSocketDisconnect:
        await chat_ws_manager.disconnect(workspace_id, user_id, websocket)
    except Exception as e:
        logger.error(f"WebSocket error in workspace {workspace_id}: {e}")
        await chat_ws_manager.disconnect(workspace_id, user_id, websocket)
