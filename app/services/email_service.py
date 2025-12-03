"""
Email service for sending OTP and password reset emails via Gmail SMTP.
"""
import smtplib
import os
import secrets
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from typing import Optional
import logging
from pathlib import Path
from dotenv import load_dotenv

# Load .env file
env_path = Path(__file__).parent.parent.parent / '.env'
load_dotenv(dotenv_path=env_path)

logger = logging.getLogger(__name__)


class EmailService:
    """Service for sending emails via Gmail SMTP."""
    
    def __init__(self):
        self.smtp_host = os.getenv('SMTP_HOST', 'smtp.gmail.com')
        self.smtp_port = int(os.getenv('SMTP_PORT', '587'))
        self.smtp_user = os.getenv('SMTP_USER')
        self.smtp_password = os.getenv('SMTP_PASSWORD')
        self.from_email = os.getenv('SMTP_FROM_EMAIL', self.smtp_user)
        
        if not self.smtp_user or not self.smtp_password:
            logger.warning("SMTP credentials not configured. Email service will not work.")
    
    def generate_otp(self) -> str:
        """Generate a 6-digit OTP code."""
        return ''.join([str(secrets.randbelow(10)) for _ in range(6)])
    
    def send_otp_email(self, to_email: str, otp_code: str) -> bool:
        """
        Send OTP email to user.
        
        Args:
            to_email: Recipient email address
            otp_code: 6-digit OTP code
            
        Returns:
            True if email sent successfully, False otherwise
        """
        if not self.smtp_user or not self.smtp_password:
            logger.error("SMTP credentials not configured")
            return False
        
        try:
            # Create message
            msg = MIMEMultipart('alternative')
            msg['Subject'] = 'Password Reset - Turbo Alan Refiner'
            msg['From'] = self.from_email
            msg['To'] = to_email
            
            # Create HTML content
            html = f"""
            <html>
              <body style="font-family: Arial, sans-serif; max-width: 600px; margin: 0 auto; padding: 20px;">
                <div style="background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); padding: 30px; border-radius: 10px 10px 0 0;">
                  <h1 style="color: white; margin: 0;">Turbo Alan Refiner</h1>
                </div>
                <div style="background: #f7fafc; padding: 30px; border-radius: 0 0 10px 10px;">
                  <h2 style="color: #2d3748; margin-top: 0;">Password Reset Request</h2>
                  <p style="color: #4a5568; font-size: 16px;">
                    You requested to reset your password. Use the following code to verify your identity:
                  </p>
                  <div style="background: white; padding: 20px; border-radius: 8px; text-align: center; margin: 20px 0;">
                    <p style="color: #718096; margin: 0; font-size: 14px;">Your verification code is:</p>
                    <h1 style="color: #667eea; font-size: 48px; letter-spacing: 8px; margin: 10px 0;">{otp_code}</h1>
                  </div>
                  <p style="color: #4a5568; font-size: 14px;">
                    This code will expire in 10 minutes. If you didn't request this, please ignore this email.
                  </p>
                  <hr style="border: none; border-top: 1px solid #e2e8f0; margin: 30px 0;">
                  <p style="color: #a0aec0; font-size: 12px; text-align: center;">
                    Turbo Alan Refiner - AI-Powered Text Refinement
                  </p>
                </div>
              </body>
            </html>
            """
            
            # Attach HTML content
            msg.attach(MIMEText(html, 'html'))
            
            # Send email
            with smtplib.SMTP(self.smtp_host, self.smtp_port) as server:
                server.starttls()
                server.login(self.smtp_user, self.smtp_password)
                server.send_message(msg)
            
            logger.info(f"OTP email sent successfully to {to_email}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to send OTP email: {e}")
            return False


# Global email service instance
email_service = EmailService()
