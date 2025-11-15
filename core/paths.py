"""
Centralized path configuration for the backend.

This module provides a single source of truth for all file paths,
ensuring everything stays within the backend directory for proper deployment.
"""
from __future__ import annotations

import os
from pathlib import Path
from typing import Optional


def get_backend_root() -> Path:
    """
    Get the backend root directory.
    
    This function determines the backend root by finding the directory
    containing this file and going up to the backend folder.
    
    Returns:
        Path: Absolute path to backend directory
    """
    # This file is in backend/core/, so parent.parent gives us backend/
    current_file = Path(__file__).resolve()
    backend_root = current_file.parent.parent
    return backend_root


def get_data_dir() -> Path:
    """
    Get the data directory within backend.
    
    Returns:
        Path: Absolute path to backend/data/
    """
    backend_root = get_backend_root()
    data_dir = backend_root / "data"
    data_dir.mkdir(parents=True, exist_ok=True)
    return data_dir


def get_output_dir(env_override: Optional[str] = None) -> Path:
    """
    Get the output directory for refined files.
    
    Args:
        env_override: Optional environment variable override
        
    Returns:
        Path: Absolute path to backend/data/output/
    """
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
    
    output_dir.mkdir(parents=True, exist_ok=True)
    return output_dir


def get_file_versions_dir() -> Path:
    """
    Get the file versions directory.
    
    Returns:
        Path: Absolute path to backend/data/file_versions/
    """
    data_dir = get_data_dir()
    versions_dir = data_dir / "file_versions"
    versions_dir.mkdir(parents=True, exist_ok=True)
    return versions_dir


def get_strategy_feedback_dir() -> Path:
    """
    Get the strategy feedback directory.
    
    Returns:
        Path: Absolute path to backend/data/strategy_feedback/
    """
    data_dir = get_data_dir()
    feedback_dir = data_dir / "strategy_feedback"
    feedback_dir.mkdir(parents=True, exist_ok=True)
    return feedback_dir


def get_logs_dir() -> Path:
    """
    Get the logs directory.
    
    Returns:
        Path: Absolute path to backend/logs/
    """
    backend_root = get_backend_root()
    logs_dir = backend_root / "logs"
    logs_dir.mkdir(parents=True, exist_ok=True)
    return logs_dir


def get_config_dir() -> Path:
    """
    Get the config directory.
    
    Returns:
        Path: Absolute path to backend/config/
    """
    backend_root = get_backend_root()
    config_dir = backend_root / "config"
    config_dir.mkdir(parents=True, exist_ok=True)
    return config_dir


def get_templates_dir() -> Path:
    """
    Get the templates directory.
    
    Returns:
        Path: Absolute path to backend/templates/
    """
    backend_root = get_backend_root()
    templates_dir = backend_root / "templates"
    templates_dir.mkdir(parents=True, exist_ok=True)
    return templates_dir


def get_scripts_dir() -> Path:
    """
    Get the scripts directory.
    
    Returns:
        Path: Absolute path to backend/scripts/
    """
    backend_root = get_backend_root()
    scripts_dir = backend_root / "scripts"
    scripts_dir.mkdir(parents=True, exist_ok=True)
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


# Convenience constants for common paths
BACKEND_ROOT = get_backend_root()
DATA_DIR = get_data_dir()
OUTPUT_DIR = get_output_dir()
FILE_VERSIONS_DIR = get_file_versions_dir()
STRATEGY_FEEDBACK_DIR = get_strategy_feedback_dir()
LOGS_DIR = get_logs_dir()
CONFIG_DIR = get_config_dir()
TEMPLATES_DIR = get_templates_dir()
SCRIPTS_DIR = get_scripts_dir()

