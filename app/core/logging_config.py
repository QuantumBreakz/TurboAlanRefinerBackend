"""
Centralized logging configuration for the backend.

This module provides a consistent logging setup across the entire application,
with proper formatting, rotation, and environment-aware configuration.
"""
from __future__ import annotations

import os
import logging
import logging.handlers
import sys
from typing import Optional, Dict, Any
from pathlib import Path

from app.core.paths import get_logs_dir

# Import MongoDB DB (lazy import inside handler to avoid circular deps if possible, 
# but here we need it for the handler class)
# We'll import it inside the handler method to be safe or use a try-except block
try:
    from app.core.mongodb_db import db as mongodb_db
except ImportError:
    mongodb_db = None

class MongoDBHandler(logging.Handler):
    """
    Custom logging handler that sends logs to MongoDB.
    """
    def __init__(self):
        super().__init__()
        # Use a separate formatter for DB logs if needed, or just raw record data
        
    def emit(self, record):
        if not mongodb_db or not mongodb_db.is_connected():
            return
            
        try:
            msg = self.format(record)
            
            # Extract extra fields if they exist in record.__dict__
            metadata = getattr(record, 'metadata', {})
            if not isinstance(metadata, dict):
                metadata = {}
                
            # Add standard fields to metadata if useful
            metadata['process'] = record.process
            metadata['thread'] = record.thread
            
            mongodb_db.write_system_log(
                level=record.levelname,
                logger_name=record.name,
                message=msg,
                module=record.module,
                function_name=record.funcName,
                line_number=record.lineno,
                traceback=record.exc_text if record.exc_info else None,
                metadata=metadata
            )
        except Exception:
            self.handleError(record)

def setup_logging(
    name: str = "refiner",
    level: Optional[int] = None,
    enable_console: Optional[bool] = None
) -> logging.Logger:
    """
    Set up and configure application logging.
    
    Args:
        name: Logger name (default: 'refiner')
        level: Log level override (None = auto-detect from environment)
        enable_console: Force console output (None = auto-detect)
    
    Returns:
        Configured logger instance
    """
    logger = logging.getLogger(name)
    
    # Avoid duplicate handlers
    if logger.handlers:
        return logger
    
    # Determine log level
    if level is None:
        env_level = os.getenv("LOG_LEVEL", "INFO").upper()
        level = getattr(logging, env_level, logging.INFO)
    
    logger.setLevel(level)
    
    # Formatter
    formatter = logging.Formatter(
        "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    )
    
    # File handler (only if not on Vercel)
    if not os.getenv("VERCEL"):
        try:
            logs_dir = get_logs_dir()
            log_file = logs_dir / f"{name}.log"
            
            file_handler = logging.handlers.RotatingFileHandler(
                log_file,
                maxBytes=10*1024*1024,  # 10MB
                backupCount=5,
                encoding="utf-8"
            )
            file_handler.setFormatter(formatter)
            logger.addHandler(file_handler)
        except Exception:
            # File logging failed, continue with console only
            pass
    
    # Console handler
    if enable_console is None:
        enable_console = os.getenv("DEBUG", "").lower() in ("1", "true", "yes") or os.getenv("VERCEL")
    
    if enable_console:
        console_handler = logging.StreamHandler(sys.stdout)
        console_handler.setFormatter(formatter)
        logger.addHandler(console_handler)
        
    # MongoDB Handler (Always add if available, but maybe restrict level to INFO/WARN in prod to save DB space)
    # For now, we add it for all logs >= INFO
    if mongodb_db and mongodb_db.is_connected():
        mongodb_handler = MongoDBHandler()
        mongodb_handler.setLevel(logging.INFO) # Don't flood DB with DEBUG
        mongodb_handler.setFormatter(formatter)
        logger.addHandler(mongodb_handler)
    
    return logger

def get_logger(name: str = "refiner") -> logging.Logger:
    """
    Get a configured logger instance.
    
    Args:
        name: Logger name
    
    Returns:
        Logger instance
    """
    logger = logging.getLogger(name)
    if not logger.handlers:
        return setup_logging(name)
    return logger
