from typing import Dict, Any
from datetime import datetime
import json
from fastapi.responses import JSONResponse

class APIError(Exception):
    """Custom exception for API errors with standardized format"""
    def __init__(self, message: str, status_code: int = 500, error_code: str = None, details: Dict[str, Any] = None):
        self.message = message
        self.status_code = status_code
        self.error_code = error_code or f"ERROR_{status_code}"
        self.details = details or {}
        super().__init__(self.message)

def _make_json_safe(obj: Any) -> Any:
    """Recursively convert objects to JSON-serializable forms."""
    try:
        json.dumps(obj)
        return obj
    except TypeError:
        pass
    # Exceptions -> string
    if isinstance(obj, BaseException):
        return str(obj)
    # Dicts
    if isinstance(obj, dict):
        return {str(_make_json_safe(k)): _make_json_safe(v) for k, v in obj.items()}
    # Lists/Tuples/Sets
    if isinstance(obj, (list, tuple, set)):
        return [_make_json_safe(v) for v in obj]
    # Fallback to string repr
    return repr(obj)

def create_error_response(message: str, status_code: int = 500, error_code: str = None, details: Dict[str, Any] = None) -> JSONResponse:
    """Create a standardized error response (always JSON-serializable)."""
    error_data = {
        "error": message,
        "status_code": status_code,
        "error_code": error_code or f"ERROR_{status_code}",
        "timestamp": datetime.now().isoformat(),
        "details": details or {}
    }
    safe_data = _make_json_safe(error_data)
    return JSONResponse(safe_data, status_code=status_code)
