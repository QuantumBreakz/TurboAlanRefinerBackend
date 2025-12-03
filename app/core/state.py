import threading
import time
import os
import asyncio
from typing import Dict, Any, Optional
from app.core.database import upsert_job, get_job

# File storage for uploaded files with thread safety
uploaded_files: Dict[str, Dict[str, Any]] = {}
jobs_snapshot: Dict[str, Dict[str, Any]] = {}
shared_state_lock = threading.Lock()
MAX_UPLOADED_FILES = 1000  # Prevent memory exhaustion
MAX_JOBS_SNAPSHOT = 500   # Prevent memory exhaustion
MAX_ACTIVE_TASKS = 100

# In-memory task registry for background jobs
active_tasks: Dict[str, asyncio.Task] = {}
# Track task creation times for reliable eviction of oldest tasks
active_task_times: Dict[str, float] = {}

# Rate limiting storage with thread safety
rate_limit_storage: Dict[str, Dict[str, Any]] = {}
rate_limit_lock = threading.RLock()
RATE_LIMIT_WINDOW = 60  # seconds
RATE_LIMIT_MAX_REQUESTS = 100  # requests per window

# Thread-safe access methods for shared state
def safe_uploaded_files_get(file_id: str) -> Optional[Dict[str, Any]]:
    """Thread-safe get from uploaded_files"""
    with shared_state_lock:
        return uploaded_files.get(file_id)

def safe_uploaded_files_set(file_id: str, file_info: Dict[str, Any]) -> None:
    """Thread-safe set to uploaded_files with size limits and LRU eviction."""
    with shared_state_lock:
        # Enforce size limits with LRU eviction
        if len(uploaded_files) >= MAX_UPLOADED_FILES:
            # Remove oldest files (LRU eviction)
            oldest_files = sorted(uploaded_files.items(), key=lambda x: x[1].get("uploaded_at", 0))
            for old_id, old_info in oldest_files[:MAX_UPLOADED_FILES // 2]:
                try:
                    if os.path.exists(old_info.get("temp_path", "")):
                        os.unlink(old_info["temp_path"])
                except Exception:
                    pass
                del uploaded_files[old_id]
        
        uploaded_files[file_id] = file_info

def safe_uploaded_files_del(file_id: str) -> bool:
    """Thread-safe delete from uploaded_files"""
    with shared_state_lock:
        if file_id in uploaded_files:
            del uploaded_files[file_id]
            return True
        return False

def safe_jobs_snapshot_set(job_id: str, job_info: Dict[str, Any]) -> None:
    """Thread-safe set to jobs_snapshot with size limits and LRU eviction."""
    with shared_state_lock:
        # Enforce size limits with LRU eviction
        if len(jobs_snapshot) >= MAX_JOBS_SNAPSHOT:
            # Remove oldest jobs (LRU eviction)
            oldest_jobs = sorted(jobs_snapshot.items(), key=lambda x: x[1].get("timestamp", 0))
            for old_id in [job_id for job_id, _ in oldest_jobs[:MAX_JOBS_SNAPSHOT // 2]]:
                del jobs_snapshot[old_id]
        
        jobs_snapshot[job_id] = job_info

def safe_jobs_snapshot_get(job_id: str) -> Optional[Dict[str, Any]]:
    """Thread-safe get from jobs_snapshot"""
    with shared_state_lock:
        return jobs_snapshot.get(job_id)

def safe_active_tasks_set(job_id: str, task: asyncio.Task) -> None:
    """Thread-safe set to active_tasks with size limits."""
    with shared_state_lock:
        # Enforce size limits
        if len(active_tasks) >= MAX_ACTIVE_TASKS:
            # Evict oldest tasks using tracked timestamps
            sorted_ids = sorted(active_task_times.items(), key=lambda kv: kv[1])
            evict_ids = [jid for jid, _ in sorted_ids[:max(1, MAX_ACTIVE_TASKS // 2)]]
            for old_id in evict_ids:
                active_tasks.pop(old_id, None)
                active_task_times.pop(old_id, None)
        
        active_tasks[job_id] = task
        active_task_times[job_id] = time.time()

def safe_active_tasks_del(job_id: str) -> bool:
    """Thread-safe delete from active_tasks"""
    with shared_state_lock:
        if job_id in active_tasks:
            del active_tasks[job_id]
            return True
        return False

# Database operation wrapper with proper error handling
def safe_upsert_job(job_id: str, job_data: Dict[str, Any]) -> bool:
    """Safely upsert job with proper error handling"""
    try:
        upsert_job(job_id, job_data)
        return True
    except Exception as e:
        from app.core.logger import log_exception
        log_exception("DATABASE_UPSERT_ERROR", e)
        # Store in memory fallback
        safe_jobs_snapshot_set(job_id, {**job_data, "db_error": str(e), "timestamp": time.time()})
        return False

def safe_get_job(job_id: str) -> Optional[Dict[str, Any]]:
    """Safely get job with fallback to memory"""
    try:
        result = get_job(job_id)
        if result:
            from dataclasses import asdict
            return asdict(result)
    except Exception as e:
        from app.core.logger import log_exception
        log_exception("DATABASE_GET_ERROR", e)
    
    # Fallback to memory
    return safe_jobs_snapshot_get(job_id)
