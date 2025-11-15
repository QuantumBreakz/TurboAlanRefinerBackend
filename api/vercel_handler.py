"""
Vercel serverless function handler for FastAPI application.

This module provides a serverless-compatible entry point for Vercel deployment.
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

# Add backend directory to Python path for Vercel
backend_root = Path(__file__).parent.parent
sys.path.insert(0, str(backend_root))

# Import FastAPI app
from api.main import app

# Export handler for Vercel (@vercel/python expects 'handler' or 'app')
handler = app
app = app  # Also export as 'app' for compatibility

