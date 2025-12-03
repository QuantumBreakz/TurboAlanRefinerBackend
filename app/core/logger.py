from __future__ import annotations

import os
import logging
import logging.handlers
import traceback
import json
import datetime as _dt
from typing import Any, Dict, Optional


def _backend_root() -> str:
    """Returns the backend directory root."""
    from app.core.paths import get_backend_root
    return str(get_backend_root())


def get_log_dir() -> str:
    """Returns the logs directory within backend folder."""
    from app.core.paths import get_logs_dir
    return str(get_logs_dir())


def get_logger(name: str = 'refiner', level: Optional[int] = None) -> logging.Logger:
    """Get a configured logger with rotation and proper formatting.
    
    Args:
        name: Logger name (default: 'refiner')
        level: Log level override (default: DEBUG if DEBUG env var, else INFO)
    
    Returns:
        Configured logger instance
    """
    logger = logging.getLogger(name)
    
    # Avoid duplicate handlers if logger already configured
    if logger.handlers:
        return logger
    
    # Set log level
    if level is None:
        level = logging.DEBUG if os.getenv('DEBUG') else logging.INFO
    logger.setLevel(level)
    
    # Suppress noisy third-party library warnings
    if name == 'refiner':
        # Suppress googleapiclient discovery_cache warnings
        googleapiclient_logger = logging.getLogger('googleapiclient.discovery_cache')
        googleapiclient_logger.setLevel(logging.WARNING)  # Only show WARNING and above
    
    # Create formatter
    formatter = logging.Formatter(
        '%(asctime)s [%(levelname)s] %(name)s: %(message)s',
        datefmt='%Y-%m-%dT%H:%M:%SZ'
    )
    
    # File handler with rotation
    log_path = os.path.join(get_log_dir(), 'refiner.log')
    file_handler = logging.handlers.RotatingFileHandler(
        log_path, 
        maxBytes=5*1024*1024,  # 5MB (reduced for better management)
        backupCount=3,  # Keep only 3 backup files
        encoding='utf-8'
    )
    file_handler.setFormatter(formatter)
    logger.addHandler(file_handler)
    
    # Console handler for development
    if os.getenv('DEBUG'):
        console_handler = logging.StreamHandler()
        console_handler.setFormatter(formatter)
        logger.addHandler(console_handler)
    
    # MongoDB Handler (if available and connected)
    try:
        from app.core.mongodb_db import db as mongodb_db
        if mongodb_db and mongodb_db.is_connected():
            from app.core.logging_config import MongoDBHandler
            mongodb_handler = MongoDBHandler()
            mongodb_handler.setLevel(logging.INFO)  # Don't flood DB with DEBUG
            mongodb_handler.setFormatter(formatter)
            logger.addHandler(mongodb_handler)
    except Exception:
        # MongoDB handler not available, continue without it
        pass
    
    return logger


def log_event(event: str, message: str, level: int = logging.INFO) -> None:
    """Log an event with the specified level.
    
    Args:
        event: Event identifier (e.g., 'STRATEGY', 'PASS_METRICS')
        message: Log message
        level: Log level (default: INFO)
    """
    try:
        logger = get_logger()
        logger.log(level, f"[{event}] {message}")
    except Exception:
        # Silent fail; UI should not break on logging
        pass
    
    # Also log to MongoDB (best effort)
    try:
        from app.core.mongodb_db import db
        if db.is_connected():
            db.write_system_log(
                level=logging.getLevelName(level),
                logger_name='refiner',
                message=f"[{event}] {message}"
            )
    except Exception:
        pass


def log_exception(event: str, exc: Exception, level: int = logging.ERROR) -> None:
    """Log an exception with full traceback.
    
    Args:
        event: Event identifier
        exc: Exception instance
        level: Log level (default: ERROR)
    """
    try:
        logger = get_logger()
        tb = traceback.format_exc()
        logger.log(level, f"[{event}] Exception: {exc}\n{tb}")
    except Exception:
        # Silent fail; UI should not break on logging
        pass

    # Also log to MongoDB (best effort)
    try:
        from app.core.mongodb_db import db
        if db.is_connected():
            db.write_system_log(
                level='ERROR',
                logger_name='refiner',
                message=f"[{event}] Exception: {exc}",
                traceback=traceback.format_exc()
            )
    except Exception:
        pass


def log_json(event: str, message: str, **kwargs: Any) -> None:
    """Log structured JSON data for analytics and ML systems.
    
    Args:
        event: Event identifier
        message: Log message
        **kwargs: Additional structured data to include
    """
    try:
        logger = get_logger()
        data = {
            "timestamp": _dt.datetime.utcnow().isoformat() + "Z",
            "event": event,
            "message": message,
            **kwargs
        }
        logger.info(json.dumps(data))
    except Exception:
        # Silent fail; UI should not break on logging
        pass


def log_metrics(event: str, metrics: Dict[str, Any]) -> None:
    """Log performance metrics in a structured format.
    
    Args:
        event: Event identifier
        metrics: Dictionary of metric name -> value pairs
    """
    try:
        logger = get_logger()
        timestamp = _dt.datetime.utcnow().isoformat() + "Z"
        data = {
            "timestamp": timestamp,
            "event": event,
            "type": "metrics",
            "metrics": metrics
        }
        logger.info(json.dumps(data))
    except Exception:
        # Silent fail; UI should not break on logging
        pass


def log_performance(event: str, duration_ms: float, **context: Any) -> None:
    """Log performance timing data.
    
    Args:
        event: Event identifier
        duration_ms: Duration in milliseconds
        **context: Additional context data
    """
    try:
        logger = get_logger()
        data = {
            "timestamp": _dt.datetime.utcnow().isoformat() + "Z",
            "event": event,
            "type": "performance",
            "duration_ms": duration_ms,
            **context
        }
        logger.info(json.dumps(data))
    except Exception:
        # Silent fail; UI should not break on logging
        pass


# Backward compatibility function
def log_event_legacy(event: str, message: str) -> None:
    """Legacy log_event function for backward compatibility."""
    log_event(event, message)





