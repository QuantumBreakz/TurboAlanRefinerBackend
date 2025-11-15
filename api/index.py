"""
Vercel serverless function entry point for FastAPI application.

This file serves as the main entry point for Vercel's serverless function.
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

# Export handler for Vercel
handler = app

