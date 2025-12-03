import threading
from typing import Optional

from app.core.settings import Settings
from app.core.language_model import OpenAIModel
from app.services.pipeline_service import RefinementPipeline

# Global instances with dependency injection and thread safety
_settings: Optional[Settings] = None
_pipeline: Optional[RefinementPipeline] = None
_model: Optional[OpenAIModel] = None
_global_lock = threading.RLock()  # Use RLock to allow reentrant calls

def get_settings() -> Settings:
    """
    Get application settings instance.
    
    Returns:
        Settings instance with current configuration
    """
    global _settings
    if _settings is None:
        with _global_lock:
            if _settings is None:  # Double-checked locking
                _settings = Settings.load()
    return _settings

def get_model() -> OpenAIModel:
    global _model
    if _model is None:
        with _global_lock:
            if _model is None:  # Double-checked locking
                settings = get_settings()
                _model = OpenAIModel(settings.openai_api_key, model=settings.openai_model)
    return _model

def get_pipeline() -> RefinementPipeline:
    """
    Get or create the refinement pipeline instance (singleton).
    
    Returns:
        RefinementPipeline instance
        
    Raises:
        ConfigurationError: If pipeline cannot be initialized
    """
    global _pipeline
    if _pipeline is None:
        with _global_lock:
            if _pipeline is None:  # Double-checked locking
                settings = get_settings()
                model = get_model()
                _pipeline = RefinementPipeline(settings, model)
    return _pipeline

def reset_globals():
    """Reset global instances (useful for reloading settings)"""
    global _settings, _model, _pipeline
    with _global_lock:
        _settings = None
        _model = None
        _pipeline = None
