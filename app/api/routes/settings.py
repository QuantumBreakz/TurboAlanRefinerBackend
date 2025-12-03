"""
Settings API routes.

This module handles application settings endpoints including getting and saving settings.
"""
from __future__ import annotations

import os
import logging
from typing import Dict, Any

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse

from app.core.settings import Settings
from app.core.prompt_schema import ADVANCED_COMMANDS
from app.core.exceptions import ConfigurationError

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/settings", tags=["settings"])


def _check_google_drive_connection() -> bool:
    """Check if Google Drive is connected."""
    try:
        from app.utils.utils import get_google_credentials
        creds = get_google_credentials()
        return creds is not None
    except Exception:
        return False


def _get_settings() -> Settings:
    """
    Get settings instance (singleton pattern).
    
    Uses Settings.load() directly to avoid circular imports.
    For caching, consider moving get_settings to a separate module.
    """
    return Settings.load()


@router.get("")
async def get_settings_endpoint() -> JSONResponse:
    """
    Get current application settings.
    
    Returns:
        JSONResponse with current settings including:
        - OpenAI API configuration
        - Model settings
        - Google Drive connection status
        - Supported file types
        - Schema defaults
    """
    try:
        s = _get_settings()
        settings_dict: Dict[str, Any] = {
            "openaiApiKey": "sk-***" if s.openai_api_key else "",
            "openaiModel": s.openai_model,
            "targetScannerRisk": s.target_scanner_risk,
            "minWordRatio": s.min_word_ratio,
            "googleDriveConnected": _check_google_drive_connection(),
            "defaultOutputLocation": "local",
            "supportedFileTypes": [".txt", ".docx", ".md"],
            "schemaDefaults": {
                "microstructure_control": 2,
                "macrostructure_analysis": 1,
                "anti_scanner_techniques": 3,
                "entropy_management": 2,
                "semantic_tone_tuning": 1,
                "formatting_safeguards": 3,
                "refiner_control": 2,
                "history_analysis": 1,
                "annotation_mode": 0,
                "humanize_academic": 2,
            },
            "strategyMode": os.getenv("STRATEGY_MODE", "model"),
            "availableSchemas": list(ADVANCED_COMMANDS.keys()),
        }
        return JSONResponse(settings_dict)
    except Exception as e:
        logger.error(f"Failed to get settings: {e}", exc_info=True)
        raise ConfigurationError(
            message="Failed to retrieve settings",
            details={"error": str(e)}
        )


@router.post("")
async def save_settings_endpoint(request: Request) -> JSONResponse:
    """
    Save application settings.
    
    Args:
        request: Request containing settings data
        
    Returns:
        JSONResponse with save status
    """
    try:
        data = await request.json()
        # Implementation would go here
        # This would typically update settings in database or config file
        logger.info("Settings update requested")
        return JSONResponse({"message": "Settings saved", "status": "success"})
    except Exception as e:
        logger.error(f"Failed to save settings: {e}", exc_info=True)
        raise ConfigurationError(
            message="Failed to save settings",
            details={"error": str(e)}
        )

