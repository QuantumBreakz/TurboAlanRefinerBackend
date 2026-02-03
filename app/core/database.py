"""
Database facade - provides unified interface to underlying database.
Now uses MongoDB as the single source of truth, with in-memory fallback for development.
"""

import os
import time
from datetime import datetime
from typing import Optional, Dict, Any, List
from dataclasses import dataclass
from pathlib import Path

# Import MongoDB as primary database
from app.core.mongodb_db import mongodb

@dataclass
class RefinementJob:
    """Represents a refinement job in the system."""
    id: str
    user_id: str
    status: str  # "pending", "running", "completed", "failed", "cancelled"
    progress: float = 0.0
    current_stage: str = "initializing"
    error_message: Optional[str] = None
    result: Optional[Dict[str, Any]] = None
    created_at: float = None
    updated_at: float = None
    completed_at: Optional[float] = None

    def __post_init__(self):
        if self.created_at is None:
            self.created_at = time.time()
        if self.updated_at is None:
            self.updated_at = time.time()
    
    @classmethod
    def from_mongo_doc(cls, doc: Dict) -> "RefinementJob":
        """Convert MongoDB document to RefinementJob."""
        # Handle datetime conversion
        created_at = doc.get('created_at')
        updated_at = doc.get('updated_at')
        
        if hasattr(created_at, 'timestamp'):
            created_at = created_at.timestamp()
        elif isinstance(created_at, str):
            try:
                created_at = datetime.fromisoformat(created_at.replace('Z', '+00:00')).timestamp()
            except:
                created_at = time.time()
        elif created_at is None:
            created_at = time.time()
        
        if hasattr(updated_at, 'timestamp'):
            updated_at = updated_at.timestamp()
        elif isinstance(updated_at, str):
            try:
                updated_at = datetime.fromisoformat(updated_at.replace('Z', '+00:00')).timestamp()
            except:
                updated_at = time.time()
        elif updated_at is None:
            updated_at = time.time()
        
        metadata = doc.get('metadata', {})
        
        return cls(
            id=doc.get('id'),
            user_id=doc.get('user_id', 'default'),
            status=doc.get('status', 'unknown'),
            progress=metadata.get('progress', 0.0),
            current_stage=metadata.get('current_stage', 'unknown'),
            error_message=metadata.get('error_message'),
            result=metadata.get('result'),
            created_at=created_at,
            updated_at=updated_at,
            completed_at=metadata.get('completed_at')
        )

# In-memory storage for jobs (fallback only when MongoDB unavailable)
_jobs_storage: Dict[str, RefinementJob] = {}

def init_database():
    """Initialize the database - now checks MongoDB connection."""
    if mongodb.is_connected():
        print("✅ Database initialized (MongoDB)")
    else:
        print("⚠️  Warning: MongoDB not connected, using in-memory fallback")
        print("   Some features may not persist across restarts")

def upsert_job(job_id: str, job_data: Dict[str, Any]) -> RefinementJob:
    """
    Create or update a job - now uses MongoDB as primary storage.
    Falls back to in-memory storage if MongoDB unavailable.
    """
    global _jobs_storage
    
    # Try MongoDB first
    if mongodb.is_connected():
        # Extract fields for MongoDB
        file_name = job_data.get('file_name', 'unknown')
        file_id = job_data.get('file_id', job_id)
        user_id = job_data.get('user_id', 'default')
        
        # Check if job exists
        existing = mongodb.get_job_by_id(job_id)
        
        if existing:
            # Update existing job
            metadata = {
                'progress': job_data.get('progress', 0.0),
                'current_stage': job_data.get('current_stage', 'unknown'),
                'error_message': job_data.get('error_message'),
                'result': job_data.get('result'),
                'completed_at': job_data.get('completed_at')
            }
            mongodb.update_job_status(
                job_id=job_id,
                status=job_data.get('status', 'pending'),
                current_pass=job_data.get('current_pass'),
                metadata_update=metadata
            )
        else:
            # Create new job
            metadata = {
                'progress': job_data.get('progress', 0.0),
                'current_stage': job_data.get('current_stage', 'initializing'),
                'result': job_data.get('result'),
                'error_message': job_data.get('error_message')
            }
            mongodb.create_job(
                job_id=job_id,
                file_name=file_name,
                file_id=file_id,
                user_id=user_id,
                total_passes=job_data.get('total_passes', 1),
                model=job_data.get('model', 'gpt-4'),
                metadata=metadata
            )
        
        # Return the updated job
        job_doc = mongodb.get_job_by_id(job_id)
        if job_doc:
            return RefinementJob.from_mongo_doc(job_doc)
    
    # Fallback to in-memory storage
    if job_id in _jobs_storage:
        # Update existing job
        job = _jobs_storage[job_id]
        for key, value in job_data.items():
            if hasattr(job, key):
                setattr(job, key, value)
        job.updated_at = time.time()
    else:
        # Create new job
        job_data['id'] = job_id
        job_data['user_id'] = job_data.get('user_id', 'default')
        job = RefinementJob(**job_data)
        _jobs_storage[job_id] = job
    
    return job

def get_job(job_id: str) -> Optional[RefinementJob]:
    """
    Get a job by ID - now reads from MongoDB first.
    Falls back to in-memory storage if MongoDB unavailable.
    """
    # Try MongoDB first
    if mongodb.is_connected():
        doc = mongodb.get_job_by_id(job_id)
        if doc:
            return RefinementJob.from_mongo_doc(doc)
    
    # Fallback to in-memory storage
    return _jobs_storage.get(job_id)

def list_jobs(user_id: Optional[str] = None, limit: int = 50) -> List[RefinementJob]:
    """
    List jobs - now reads from MongoDB first.
    Falls back to in-memory storage if MongoDB unavailable.
    """
    # Try MongoDB first
    if mongodb.is_connected():
        docs = mongodb.get_jobs(limit=limit, user_id=user_id)
        return [RefinementJob.from_mongo_doc(doc) for doc in docs]
    
    # Fallback to in-memory storage
    jobs = list(_jobs_storage.values())
    
    if user_id:
        jobs = [job for job in jobs if job.user_id == user_id]
    
    # Sort by created_at descending
    jobs.sort(key=lambda x: x.created_at, reverse=True)
    
    return jobs[:limit]

def delete_job(job_id: str) -> bool:
    """
    Delete a job by ID from both MongoDB and memory.
    """
    deleted = False
    
    # Delete from MongoDB first
    if mongodb.is_connected():
        deleted = mongodb.delete_job(job_id)
    
    # Delete from memory
    if job_id in _jobs_storage:
        del _jobs_storage[job_id]
        deleted = True
    
    return deleted

def cleanup_old_jobs(days_to_keep: int = 30):
    """
    Clean up old completed/failed jobs from both MongoDB and memory.
    """
    deleted_count = 0
    
    # Clean up MongoDB first
    if mongodb.is_connected():
        deleted_count = mongodb.cleanup_old_jobs(days_to_keep)
    
    # Clean up memory
    cutoff_time = time.time() - (days_to_keep * 24 * 3600)
    
    jobs_to_remove = []
    for job_id, job in _jobs_storage.items():
        if (job.status in ['completed', 'failed', 'cancelled'] and 
            job.created_at < cutoff_time):
            jobs_to_remove.append(job_id)
    
    for job_id in jobs_to_remove:
        del _jobs_storage[job_id]
    
    return deleted_count + len(jobs_to_remove)
