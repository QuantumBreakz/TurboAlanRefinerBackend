"""
Centralized path configuration for the backend.

This module provides a single source of truth for all file paths,
ensuring everything stays within the backend directory for proper deployment.
"""
from __future__ import annotations

import os
from pathlib import Path
from typing import Optional


def _is_vercel() -> bool:
    """Check if running on Vercel serverless environment."""
    return os.getenv("VERCEL") == "1" or "/var/task" in str(Path(__file__).resolve())


def _get_writable_base_dir() -> Path:
    """
    Get a writable base directory for file operations.
    
    On Vercel, use /tmp which is writable.
    Otherwise, use the backend directory.
    """
    if _is_vercel():
        return Path("/tmp")
    return get_backend_root()


def get_backend_root() -> Path:
    """
    Get the backend root directory.
    
    This function determines the backend root by finding the directory
    containing this file and going up to the backend folder.
    
    Returns:
        Path: Absolute path to backend directory
    """
    # This file is in backend/app/core/, so parent.parent.parent gives us backend/
    current_file = Path(__file__).resolve()
    backend_root = current_file.parent.parent.parent
    return backend_root


def get_data_dir() -> Path:
    """
    Get the data directory within backend.
    
    On Vercel, uses /tmp/data for writable storage.
    Otherwise, uses backend/data/
    
    Returns:
        Path: Absolute path to data directory
    """
    if _is_vercel():
        data_dir = Path("/tmp/data")
    else:
        backend_root = get_backend_root()
        data_dir = backend_root / "data"
    
    # Only try to create directory if not on read-only filesystem
    try:
        data_dir.mkdir(parents=True, exist_ok=True)
    except OSError:
        # If we can't create it, return the path anyway (might be read-only)
        pass
    return data_dir


def get_output_dir(env_override: Optional[str] = None) -> Path:
    """
    Get the output directory for refined files.
    
    On Vercel, uses /tmp/output for writable storage.
    Otherwise, uses backend/data/output/
    
    Args:
        env_override: Optional environment variable override
        
    Returns:
        Path: Absolute path to output directory
    """
    if _is_vercel():
        output_dir = Path("/tmp/output")
    else:
        backend_root = get_backend_root()
        
        # Check environment variable first
        if env_override:
            output_dir = Path(env_override)
            # If relative, make it relative to backend
            if not output_dir.is_absolute():
                output_dir = backend_root / output_dir
            # Ensure it's within backend directory for security
            if not str(output_dir).startswith(str(backend_root)):
                output_dir = backend_root / "data" / "output"
        else:
            env_path = os.getenv("REFINER_OUTPUT_DIR")
            if env_path:
                output_dir = Path(env_path)
                # If relative, make it relative to backend
                if not output_dir.is_absolute():
                    output_dir = backend_root / output_dir
                # Ensure it's within backend directory for security
                if not str(output_dir).startswith(str(backend_root)):
                    output_dir = backend_root / "data" / "output"
            else:
                # Default to backend/data/output
                output_dir = backend_root / "data" / "output"
    
    # Only try to create directory if not on read-only filesystem
    try:
        output_dir.mkdir(parents=True, exist_ok=True)
    except OSError:
        # If we can't create it, return the path anyway (might be read-only)
        pass
    return output_dir


def get_file_versions_dir() -> Path:
    """
    Get the file versions directory.
    
    Returns:
        Path: Absolute path to file_versions directory
    """
    data_dir = get_data_dir()
    versions_dir = data_dir / "file_versions"
    # Only try to create directory if not on read-only filesystem
    try:
        versions_dir.mkdir(parents=True, exist_ok=True)
    except OSError:
        # If we can't create it, return the path anyway (might be read-only)
        pass
    return versions_dir


def get_strategy_feedback_dir() -> Path:
    """
    Get the strategy feedback directory.
    
    Returns:
        Path: Absolute path to strategy_feedback directory
    """
    data_dir = get_data_dir()
    feedback_dir = data_dir / "strategy_feedback"
    # Only try to create directory if not on read-only filesystem
    try:
        feedback_dir.mkdir(parents=True, exist_ok=True)
    except OSError:
        # If we can't create it, return the path anyway (might be read-only)
        pass
    return feedback_dir


def get_logs_dir() -> Path:
    """
    Get the logs directory.
    
    On Vercel, uses /tmp/logs for writable storage.
    Otherwise, uses backend/logs/
    
    Returns:
        Path: Absolute path to logs directory
    """
    if _is_vercel():
        logs_dir = Path("/tmp/logs")
    else:
        backend_root = get_backend_root()
        logs_dir = backend_root / "logs"
    
    # Only try to create directory if not on read-only filesystem
    try:
        logs_dir.mkdir(parents=True, exist_ok=True)
    except OSError:
        # If we can't create it, return the path anyway (might be read-only)
        pass
    return logs_dir


def get_config_dir() -> Path:
    """
    Get the config directory.
    
    Returns:
        Path: Absolute path to config directory
    """
    backend_root = get_backend_root()
    config_dir = backend_root / "config"
    # Only try to create directory if not on read-only filesystem
    try:
        config_dir.mkdir(parents=True, exist_ok=True)
    except OSError:
        # If we can't create it, return the path anyway (might be read-only)
        pass
    return config_dir


def get_templates_dir() -> Path:
    """
    Get the templates directory.
    
    Returns:
        Path: Absolute path to templates directory
    """
    backend_root = get_backend_root()
    templates_dir = backend_root / "templates"
    # Only try to create directory if not on read-only filesystem
    try:
        templates_dir.mkdir(parents=True, exist_ok=True)
    except OSError:
        # If we can't create it, return the path anyway (might be read-only)
        pass
    return templates_dir


def get_scripts_dir() -> Path:
    """
    Get the scripts directory.
    
    Returns:
        Path: Absolute path to scripts directory
    """
    backend_root = get_backend_root()
    scripts_dir = backend_root / "scripts"
    # Only try to create directory if not on read-only filesystem
    try:
        scripts_dir.mkdir(parents=True, exist_ok=True)
    except OSError:
        # If we can't create it, return the path anyway (might be read-only)
        pass
    return scripts_dir


def sanitize_path(path: str, base_dir: Optional[Path] = None) -> Path:
    """
    Sanitize a path to ensure it's within the backend directory.
    
    Args:
        path: Path to sanitize
        base_dir: Base directory to check against (defaults to backend root)
        
    Returns:
        Path: Sanitized absolute path within backend directory
    """
    if base_dir is None:
        base_dir = get_backend_root()
    
    path_obj = Path(path)
    
    # Convert to absolute path
    if not path_obj.is_absolute():
        path_obj = base_dir / path_obj
    
    # Resolve any .. components
    path_obj = path_obj.resolve()
    
    # Ensure it's within base directory
    try:
        path_obj.relative_to(base_dir)
    except ValueError:
        # Path is outside base directory, use default
        path_obj = base_dir / "data" / "output"
    
    return path_obj


# Note: We don't create module-level constants that execute at import time
# because Vercel's filesystem is read-only. Instead, call the functions
# when needed to get paths lazily.

