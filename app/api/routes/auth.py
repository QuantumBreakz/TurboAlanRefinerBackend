"""
Password reset API routes.
"""
from __future__ import annotations

import time
import secrets
from typing import Dict
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, EmailStr

from app.services.email_service import email_service
from app.core.logger import get_logger

logger = get_logger('api.auth')

router = APIRouter(prefix="/auth", tags=["auth"])

# In-memory OTP storage (use Redis in production)
# Structure: {email: {otp: str, expires_at: float, temp_token: str}}
otp_storage: Dict[str, Dict[str, any]] = {}

# OTP expiration time (10 minutes)
OTP_EXPIRATION_SECONDS = 600


class PasswordResetRequest(BaseModel):
    email: EmailStr


class OTPVerification(BaseModel):
    email: EmailStr
    otp: str


class PasswordReset(BaseModel):
    email: EmailStr
    token: str
    new_password: str


@router.post("/request-password-reset")
async def request_password_reset(request: PasswordResetRequest):
    """
    Request a password reset OTP.
    
    Sends a 6-digit OTP to the user's email address.
    """
    try:
        email = request.email.lower()
        
        # Generate OTP
        otp = email_service.generate_otp()
        
        # Store OTP with expiration
        otp_storage[email] = {
            "otp": otp,
            "expires_at": time.time() + OTP_EXPIRATION_SECONDS,
            "temp_token": None
        }
        
        # Send OTP email
        success = email_service.send_otp_email(email, otp)
        
        if not success:
            raise HTTPException(
                status_code=500,
                detail="Failed to send OTP email. Please check SMTP configuration."
            )
        
        logger.info(f"Password reset OTP sent to {email}")
        
        return {
            "message": "OTP sent successfully",
            "email": email,
            "expires_in": OTP_EXPIRATION_SECONDS
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Password reset request failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/verify-otp")
async def verify_otp(verification: OTPVerification):
    """
    Verify OTP code and return a temporary token.
    
    The temporary token can be used to reset the password.
    """
    try:
        email = verification.email.lower()
        
        # Check if OTP exists
        if email not in otp_storage:
            raise HTTPException(status_code=400, detail="No OTP found for this email")
        
        stored_data = otp_storage[email]
        
        # Check if OTP expired
        if time.time() > stored_data["expires_at"]:
            del otp_storage[email]
            raise HTTPException(status_code=400, detail="OTP expired. Please request a new one.")
        
        # Verify OTP
        if stored_data["otp"] != verification.otp:
            raise HTTPException(status_code=400, detail="Invalid OTP")
        
        # Generate temporary token
        temp_token = secrets.token_urlsafe(32)
        stored_data["temp_token"] = temp_token
        stored_data["token_expires_at"] = time.time() + 300  # 5 minutes
        
        logger.info(f"OTP verified for {email}")
        
        return {
            "message": "OTP verified successfully",
            "temp_token": temp_token,
            "expires_in": 300
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"OTP verification failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/reset-password")
async def reset_password(reset: PasswordReset):
    """
    Reset password using verified temporary token.
    
    This endpoint updates the password in Supabase.
    """
    try:
        email = reset.email.lower()
        
        # Check if token exists
        if email not in otp_storage:
            raise HTTPException(status_code=400, detail="Invalid or expired reset session")
        
        stored_data = otp_storage[email]
        
        # Verify temp token
        if not stored_data.get("temp_token") or stored_data["temp_token"] != reset.token:
            raise HTTPException(status_code=400, detail="Invalid reset token")
        
        # Check if token expired
        if time.time() > stored_data.get("token_expires_at", 0):
            del otp_storage[email]
            raise HTTPException(status_code=400, detail="Reset token expired")
        
        # Update password in MongoDB
        try:
            import bcrypt
            from app.core.mongodb_db import db
            
            if not db.is_connected():
                raise HTTPException(status_code=500, detail="Database connection unavailable")
            
            # Get user by email
            user = db.get_user_by_email(email)
            if not user:
                raise HTTPException(status_code=404, detail="User not found")
            
            # Hash the new password
            password_hash = bcrypt.hashpw(
                reset.new_password.encode('utf-8'), 
                bcrypt.gensalt()
            ).decode('utf-8')
            
            # Update password in MongoDB
            success = db.update_user_password(email, password_hash)
            if not success:
                raise HTTPException(status_code=500, detail="Failed to update password")
            
            logger.info(f"Password updated in MongoDB for {email}")
            
        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"Failed to update password in MongoDB: {e}")
            raise HTTPException(status_code=500, detail=f"Password update failed: {str(e)}")
        
        # Clean up OTP storage
        del otp_storage[email]
        
        logger.info(f"Password reset flow completed for {email}")
        
        return {
            "message": "Password reset successful. Please use your new password to sign in.",
            "email": email
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Password reset failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))
