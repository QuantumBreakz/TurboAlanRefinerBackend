"""
Chat API routes.

This module handles chat session management including creating, listing,
switching between sessions, and managing messages.
"""
from __future__ import annotations

import logging
from typing import Dict, Any, Optional, List
from datetime import datetime

from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import JSONResponse
from pydantic import BaseModel

from app.core.mongodb_db import db as mongodb_db
from app.core.exceptions import ProcessingError, NotFoundError
from app.core.dependencies import get_settings
from openai import OpenAI

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/chat", tags=["chat"])


# --- Helper Functions ---

def serialize_datetime(obj: Any) -> Any:
    """Recursively convert datetime objects to ISO strings for JSON serialization."""
    if isinstance(obj, datetime):
        return obj.isoformat()
    elif isinstance(obj, dict):
        return {key: serialize_datetime(value) for key, value in obj.items()}
    elif isinstance(obj, list):
        return [serialize_datetime(item) for item in obj]
    return obj


# --- Request Models ---

class CreateSessionRequest(BaseModel):
    """Request model for creating a new chat session."""
    title: Optional[str] = None
    workspace_id: Optional[str] = None


class ChatMessageRequest(BaseModel):
    """Request model for adding a message to a session."""
    role: str  # "user", "assistant", "system"
    content: str
    metadata: Optional[Dict[str, Any]] = None


class RenameSessionRequest(BaseModel):
    """Request model for renaming a session."""
    title: str


# --- Session Management Routes ---

@router.post("/sessions")
async def create_session(
    request: CreateSessionRequest,
    user_id: str = Query(..., description="User ID")
) -> JSONResponse:
    """
    Create a new chat session.
    
    Args:
        request: Session creation data
        user_id: ID of the user creating the session
        
    Returns:
        JSONResponse with created session data
    """
    try:
        logger.info(f"Creating chat session for user {user_id}")
        
        if not mongodb_db.is_connected():
            raise ProcessingError(
                message="MongoDB not connected",
                details={"error": "Database connection unavailable"}
            )
        
        session_id = mongodb_db.create_chat_session(
            user_id=user_id,
            title=request.title,
            workspace_id=request.workspace_id
        )
        
        if not session_id:
            raise ProcessingError(
                message="Failed to create chat session",
                details={"error": "Database operation failed"}
            )
        
        # Get the created session
        session = mongodb_db.get_session(session_id)
        
        logger.info(f"Created session {session_id} for user {user_id}")
        return JSONResponse(serialize_datetime(session))
        
    except Exception as e:
        logger.error(f"Create session error: {e}", exc_info=True)
        raise ProcessingError(
            message="Failed to create chat session",
            details={"error": str(e)}
        )


@router.get("/sessions")
async def list_sessions(
    user_id: str = Query(..., description="User ID"),
    limit: int = Query(50, description="Maximum number of sessions to return")
) -> JSONResponse:
    """
    List all chat sessions for a user.
    
    Args:
        user_id: ID of the user
        limit: Maximum number of sessions to return (default: 50)
        
    Returns:
        JSONResponse with list of sessions
    """
    try:
        logger.info(f"[SECURITY] Listing sessions for user_id: {user_id}")
        
        if not mongodb_db.is_connected():
            return JSONResponse({"sessions": []})
        
        # CRITICAL: Only return sessions for THIS user
        sessions = mongodb_db.get_user_sessions(user_id=user_id, limit=limit)
        
        # Double-check all returned sessions belong to this user
        filtered_sessions = [s for s in sessions if s.get("user_id") == user_id]
        if len(filtered_sessions) != len(sessions):
            logger.error(f"[SECURITY] Found {len(sessions) - len(filtered_sessions)} sessions with mismatched user_id!")
        
        logger.info(f"Returning {len(filtered_sessions)} sessions for user {user_id}")
        return JSONResponse(serialize_datetime({"sessions": filtered_sessions}))
        
    except Exception as e:
        logger.error(f"List sessions error: {e}", exc_info=True)
        raise ProcessingError(
            message="Failed to list chat sessions",
            details={"error": str(e)}
        )


@router.get("/sessions/{session_id}")
async def get_session(
    session_id: str,
    user_id: str = Query(..., description="User ID")
) -> JSONResponse:
    """
    Get a specific chat session.
    
    Args:
        session_id: ID of the session
        user_id: ID of the user (for verification)
        
    Returns:
        JSONResponse with session data
        
    Raises:
        NotFoundError: If session not found or not owned by user
    """
    try:
        if not mongodb_db.is_connected():
            raise NotFoundError("Chat session", session_id)
        
        session = mongodb_db.get_session(session_id)
        
        if not session:
            raise NotFoundError("Chat session", session_id)
        
        # Verify ownership
        if session.get("user_id") != user_id:
            raise HTTPException(
                status_code=403,
                detail="You don't have permission to access this session"
            )
        
        return JSONResponse(serialize_datetime(session))
        
    except NotFoundError:
        raise
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Get session error: {e}", exc_info=True)
        raise ProcessingError(
            message="Failed to get chat session",
            details={"error": str(e)}
        )


@router.patch("/sessions/{session_id}")
async def rename_session(
    session_id: str,
    request: RenameSessionRequest,
    user_id: str = Query(..., description="User ID")
) -> JSONResponse:
    """
    Rename a chat session.
    
    Args:
        session_id: ID of the session
        request: New title
        user_id: ID of the user (for verification)
        
    Returns:
        JSONResponse with success status
        
    Raises:
        NotFoundError: If session not found or not owned by user
    """
    try:
        if not mongodb_db.is_connected():
            raise NotFoundError("Chat session", session_id)
        
        success = mongodb_db.rename_session(
            session_id=session_id,
            user_id=user_id,
            new_title=request.title
        )
        
        if not success:
            raise NotFoundError("Chat session", session_id)
        
        return JSONResponse({"success": True, "session_id": session_id})
        
    except NotFoundError:
        raise
    except Exception as e:
        logger.error(f"Rename session error: {e}", exc_info=True)
        raise ProcessingError(
            message="Failed to rename chat session",
            details={"error": str(e)}
        )


@router.delete("/sessions/{session_id}")
async def delete_session(
    session_id: str,
    user_id: str = Query(..., description="User ID")
) -> JSONResponse:
    """
    Delete a chat session and all its messages.
    
    Args:
        session_id: ID of the session
        user_id: ID of the user (for verification)
        
    Returns:
        JSONResponse with success status
        
    Raises:
        NotFoundError: If session not found or not owned by user
    """
    try:
        if not mongodb_db.is_connected():
            raise NotFoundError("Chat session", session_id)
        
        success = mongodb_db.delete_session(
            session_id=session_id,
            user_id=user_id
        )
        
        if not success:
            raise NotFoundError("Chat session", session_id)
        
        logger.info(f"Deleted session {session_id} for user {user_id}")
        return JSONResponse({"success": True, "session_id": session_id})
        
    except NotFoundError:
        raise
    except Exception as e:
        logger.error(f"Delete session error: {e}", exc_info=True)
        raise ProcessingError(
            message="Failed to delete chat session",
            details={"error": str(e)}
        )


@router.delete("/sessions/{session_id}/messages")
async def clear_session_messages(
    session_id: str,
    user_id: str = Query(..., description="User ID")
) -> JSONResponse:
    """
    Clear all messages in a session while keeping the session.
    
    Args:
        session_id: ID of the session
        user_id: ID of the user (for verification)
        
    Returns:
        JSONResponse with success status
        
    Raises:
        NotFoundError: If session not found or not owned by user
    """
    try:
        if not mongodb_db.is_connected():
            raise NotFoundError("Chat session", session_id)
        
        success = mongodb_db.clear_session_messages(
            session_id=session_id,
            user_id=user_id
        )
        
        if not success:
            raise NotFoundError("Chat session", session_id)
        
        return JSONResponse({"success": True, "session_id": session_id})
        
    except NotFoundError:
        raise
    except Exception as e:
        logger.error(f"Clear messages error: {e}", exc_info=True)
        raise ProcessingError(
            message="Failed to clear session messages",
            details={"error": str(e)}
        )


# --- Message Management Routes ---

@router.get("/sessions/{session_id}/messages")
async def get_messages(
    session_id: str,
    user_id: str = Query(..., description="User ID"),
    limit: int = Query(100, description="Maximum number of messages to return")
) -> JSONResponse:
    """
    Get all messages in a chat session.
    
    Args:
        session_id: ID of the session
        user_id: ID of the user (for verification)
        limit: Maximum number of messages to return (default: 100)
        
    Returns:
        JSONResponse with list of messages
        
    Raises:
        NotFoundError: If session not found or not owned by user
    """
    try:
        if not mongodb_db.is_connected():
            return JSONResponse({"messages": []})
        
        # Verify session exists and user owns it
        session = mongodb_db.get_session(session_id)
        if not session:
            raise NotFoundError("Chat session", session_id)
        
        if session.get("user_id") != user_id:
            raise HTTPException(
                status_code=403,
                detail="You don't have permission to access this session"
            )
        
        messages = mongodb_db.get_session_messages(
            session_id=session_id,
            limit=limit
        )
        
        return JSONResponse(serialize_datetime({"messages": messages}))
        
    except NotFoundError:
        raise
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Get messages error: {e}", exc_info=True)
        raise ProcessingError(
            message="Failed to get session messages",
            details={"error": str(e)}
        )


@router.post("/sessions/{session_id}/messages")
async def add_message(
    session_id: str,
    request: ChatMessageRequest,
    user_id: str = Query(..., description="User ID")
) -> JSONResponse:
    """
    Add a message to a chat session and generate AI response.
    
    Args:
        session_id: ID of the session
        request: Message data
        user_id: ID of the user
        
    Returns:
        JSONResponse with created message ID and AI response
        
    Raises:
        NotFoundError: If session not found
    """
    try:
        if not mongodb_db.is_connected():
            raise ProcessingError(
                message="MongoDB not connected",
                details={"error": "Database connection unavailable"}
            )
        
        # Verify session exists
        session = mongodb_db.get_session(session_id)
        if not session:
            raise NotFoundError("Chat session", session_id)
        
        # Verify ownership for user messages
        if request.role == "user" and session.get("user_id") != user_id:
            raise HTTPException(
                status_code=403,
                detail="You don't have permission to add messages to this session"
            )
        
        # Save user message
        user_message_id = mongodb_db.add_chat_message(
            session_id=session_id,
            user_id=user_id,
            role=request.role,
            content=request.content,
            metadata=request.metadata
        )
        
        if not user_message_id:
            raise ProcessingError(
                message="Failed to add message",
                details={"error": "Database operation failed"}
            )
        
        # Generate AI response if this is a user message
        assistant_message_id = None
        assistant_content = None
        
        if request.role == "user":
            try:
                # Get conversation history
                messages = mongodb_db.get_session_messages(session_id, limit=50)
                
                # Build OpenAI messages format with system prompt
                openai_messages = [
                    {
                        "role": "system",
                        "content": """You are an AI assistant for Turbo Alan Refiner, a document refinement platform. 

Your role is to help users with:
- Understanding the document refinement process
- Answering questions about schemas, passes, and settings
- Explaining results and metrics
- Providing guidance on how to use the platform
- Troubleshooting issues

Be helpful, concise, and professional. Focus on document refinement topics."""
                    }
                ]
                
                # Add conversation history
                for msg in messages:
                    openai_messages.append({
                        "role": msg["role"],
                        "content": msg["content"]
                    })
                
                # Get OpenAI API key
                settings = get_settings()
                if not settings.openai_api_key:
                    logger.warning("OpenAI API key not configured, skipping AI response")
                else:
                    # Generate AI response
                    client = OpenAI(api_key=settings.openai_api_key)
                    response = client.chat.completions.create(
                        model="gpt-4",
                        messages=openai_messages,
                        temperature=0.7,
                        max_tokens=1000
                    )
                    
                    assistant_content = response.choices[0].message.content
                    
                    # Save assistant response
                    assistant_message_id = mongodb_db.add_chat_message(
                        session_id=session_id,
                        user_id=user_id,
                        role="assistant",
                        content=assistant_content,
                        metadata={"model": "gpt-4"}
                    )
                    
                    logger.info(f"Generated AI response for session {session_id}")
                    
            except Exception as e:
                logger.error(f"Failed to generate AI response: {e}", exc_info=True)
                # Don't fail the whole request - user message was saved
                assistant_content = "Sorry, I encountered an error generating a response. Please try again."
                assistant_message_id = mongodb_db.add_chat_message(
                    session_id=session_id,
                    user_id=user_id,
                    role="assistant",
                    content=assistant_content,
                    metadata={"error": str(e)}
                )
        
        response_data = {
            "success": True,
            "message_id": user_message_id,
            "session_id": session_id
        }
        
        if assistant_message_id and assistant_content:
            response_data["assistant_message_id"] = assistant_message_id
            response_data["assistant_content"] = assistant_content
        
        return JSONResponse(response_data)
        
    except NotFoundError:
        raise
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Add message error: {e}", exc_info=True)
        raise ProcessingError(
            message="Failed to add message",
            details={"error": str(e)}
        )

# ============================================================================
# Collaborative Session Endpoints
# ============================================================================

class ShareSessionRequest(BaseModel):
    """Request model for sharing a session"""
    participant_emails: List[str] = []  # Emails to invite

class AddParticipantRequest(BaseModel):
    """Request model for adding a participant"""
    email: str
    user_id: Optional[str] = None  # Optional: if you know the user_id

@router.post("/sessions/{session_id}/share")
async def share_session(
    session_id: str,
    request: ShareSessionRequest,
    user_id: str = Query(..., description="User ID (owner)")
) -> JSONResponse:
    """
    Enable sharing for a session and optionally invite participants.
    
    Args:
        session_id: ID of the session to share
        request: List of participant emails to invite
        user_id: ID of the user (must be owner)
        
    Returns:
        JSONResponse with success status
    """
    try:
        # Enable sharing (MongoDB check happens inside the method)
        success = mongodb_db.share_session(session_id, user_id)
        if not success:
            raise NotFoundError("Chat session", session_id)
        
        # TODO: Add participants by email (requires user lookup)
        # For now, just enable sharing
        
        logger.info(f"Enabled sharing for session {session_id}")
        
        return JSONResponse({
            "success": True,
            "session_id": session_id,
            "is_shared": True,
            "message": "Session sharing enabled"
        })
        
    except NotFoundError:
        raise
    except Exception as e:
        logger.error(f"Share session error: {e}", exc_info=True)
        raise ProcessingError(
            message="Failed to share session",
            details={"error": str(e)}
        )

@router.delete("/sessions/{session_id}/share")
async def unshare_session(
    session_id: str,
    user_id: str = Query(..., description="User ID (owner)")
) -> JSONResponse:
    """
    Disable sharing for a session (make it private again).
    
    Args:
        session_id: ID of the session
        user_id: ID of the user (must be owner)
        
    Returns:
        JSONResponse with success status
    """
    try:
        success = mongodb_db.unshare_session(session_id, user_id)
        if not success:
            raise NotFoundError("Chat session", session_id)
        
        logger.info(f"Disabled sharing for session {session_id}")
        
        return JSONResponse({
            "success": True,
            "session_id": session_id,
            "is_shared": False,
            "message": "Session is now private"
        })
        
    except NotFoundError:
        raise
    except Exception as e:
        logger.error(f"Unshare session error: {e}", exc_info=True)
        raise ProcessingError(
            message="Failed to unshare session",
            details={"error": str(e)}
        )

@router.get("/sessions/{session_id}/participants")
async def get_session_participants(
    session_id: str,
    user_id: str = Query(..., description="User ID")
) -> JSONResponse:
    """
    Get list of participants in a session.
    
    Args:
        session_id: ID of the session
        user_id: ID of the requesting user
        
    Returns:
        JSONResponse with participants list
    """
    try:
        # Verify user has access to this session
        session = mongodb_db.get_session(session_id)
        if not session:
            raise NotFoundError("Chat session", session_id)
        
        participants_list = session.get("participants", [])
        if user_id not in participants_list:
            raise HTTPException(
                status_code=403,
                detail="You don't have access to this session"
            )
        
        participants = mongodb_db.get_session_participants(session_id)
        
        # Serialize datetime objects
        participants_serialized = serialize_datetime(participants)
        
        return JSONResponse({
            "success": True,
            "session_id": session_id,
            "participants": participants_serialized,
            "count": len(participants)
        })
        
    except NotFoundError:
        raise
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Get participants error: {e}", exc_info=True)
        raise ProcessingError(
            message="Failed to get participants",
            details={"error": str(e)}
        )

@router.post("/sessions/{session_id}/participants")
async def add_session_participant(
    session_id: str,
    request: AddParticipantRequest,
    user_id: str = Query(..., description="User ID (owner)")
) -> JSONResponse:
    """
    Add a participant to a shared session.
    
    Args:
        session_id: ID of the session
        request: Participant details (email or user_id)
        user_id: ID of the user (must be owner)
        
    Returns:
        JSONResponse with success status
    """
    try:
        # IMPORTANT: For MVP, we use email as the identifier
        # This means only users logged in with this email can access the session
        # In production, you would:
        # 1. Look up the user by email in your user database
        # 2. Get their actual user_id
        # 3. Add that user_id to participants
        
        # For now: email = user_id (they must log in with this exact email)
        participant_email = request.email.lower().strip()  # Normalize email
        participant_id = request.user_id or participant_email
        
        success = mongodb_db.add_session_participant(
            session_id=session_id,
            user_id=participant_id,
            user_email=participant_email,
            user_name=participant_email.split('@')[0]  # Simple name extraction
        )
        
        if not success:
            raise ProcessingError(
                message="Failed to add participant",
                details={"error": "Could not add participant to session"}
            )
        
        logger.info(f"Added participant {participant_id} to session {session_id}")
        
        return JSONResponse({
            "success": True,
            "session_id": session_id,
            "participant_id": participant_id,
            "message": "Participant added successfully"
        })
        
    except Exception as e:
        logger.error(f"Add participant error: {e}", exc_info=True)
        raise ProcessingError(
            message="Failed to add participant",
            details={"error": str(e)}
        )

@router.delete("/sessions/{session_id}/participants/{participant_id}")
async def remove_session_participant(
    session_id: str,
    participant_id: str,
    user_id: str = Query(..., description="User ID (owner)")
) -> JSONResponse:
    """
    Remove a participant from a session.
    
    Args:
        session_id: ID of the session
        participant_id: ID of the participant to remove
        user_id: ID of the user (must be owner)
        
    Returns:
        JSONResponse with success status
    """
    try:
        success = mongodb_db.remove_session_participant(
            session_id=session_id,
            user_id=participant_id,
            requester_id=user_id
        )
        
        if not success:
            raise ProcessingError(
                message="Failed to remove participant",
                details={"error": "Could not remove participant"}
            )
        
        logger.info(f"Removed participant {participant_id} from session {session_id}")
        
        return JSONResponse({
            "success": True,
            "session_id": session_id,
            "participant_id": participant_id,
            "message": "Participant removed successfully"
        })
        
    except Exception as e:
        logger.error(f"Remove participant error: {e}", exc_info=True)
        raise ProcessingError(
            message="Failed to remove participant",
            details={"error": str(e)}
        )
