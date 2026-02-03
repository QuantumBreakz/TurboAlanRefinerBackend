"""
Database logging utilities.
Provides safe logging for database modules to avoid recursion.
"""
import os


def safe_db_log(msg: str, module: str = "Database", always_print: bool = False):
    """
    Safe logging for database modules to avoid recursion.
    
    Args:
        msg: Message to log
        module: Module name for log prefix (e.g., "MongoDB", "Supabase")
        always_print: If True, always print regardless of DEBUG setting
    """
    if always_print or os.getenv("DEBUG", "").lower() in ("true", "1", "yes"):
        print(f"[{module}] {msg}")
