"""
Jobs API routes.

This module handles job management endpoints including job listing, status checking,
queueing, cancellation, and retry operations.
"""
from __future__ import annotations

import logging
from typing import Dict, Any

from fastapi import APIRouter, HTTPException
from fastapi.responses import JSONResponse

from app.core.mongodb_db import db as mongodb_db
from app.core.exceptions import NotFoundError, ProcessingError
from app.api.routes.refine import run_job_background, RefinementRequest
from app.core.state import active_tasks, safe_active_tasks_set
import asyncio
import uuid

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/jobs", tags=["jobs"])


@router.get("")
async def jobs_list() -> JSONResponse:
    """
    List all jobs.
    
    Returns:
        JSONResponse with list of jobs (limited to 100 most recent)
    """
    try:
        if mongodb_db.is_connected():
            jobs = mongodb_db.get_jobs(100)
        else:
            jobs = []
        return JSONResponse({"jobs": jobs})
    except Exception as e:
        logger.error(f"Failed to list jobs: {e}", exc_info=True)
        raise ProcessingError(
            message="Failed to retrieve jobs list",
            details={"error": str(e)}
        )


@router.get("/{job_id}/status")
async def get_job_status(job_id: str) -> JSONResponse:
    """
    Get status of a specific job.
    
    Args:
        job_id: Unique job identifier
        
    Returns:
        JSONResponse with job status information
        
    Raises:
        NotFoundError: If job is not found
    """
    try:
        if not mongodb_db.is_connected():
            raise NotFoundError("Job", job_id)
        
        # Get job from MongoDB
        jobs = mongodb_db.get_jobs(1)
        job = next((j for j in jobs if j.get("id") == job_id), None)
        
        if not job:
            raise NotFoundError("Job", job_id)
        
        return JSONResponse(job)
    except NotFoundError:
        raise
    except Exception as e:
        logger.error(f"Failed to get job status: {e}", exc_info=True)
        raise ProcessingError(
            message="Failed to retrieve job status",
            details={"job_id": job_id, "error": str(e)}
        )


@router.post("/queue")
async def queue_job(request: RefinementRequest) -> JSONResponse:
    """
    Queue a new job for processing.
    
    Args:
        request: Job request data
        
    Returns:
        JSONResponse with queued job information
    """
    try:
        job_id = str(uuid.uuid4())
        
        # Create job in MongoDB
        if mongodb_db.is_connected():
            mongodb_db.create_job(
                job_id=job_id,
                file_name=request.files[0].get("name", "unknown") if request.files else "unknown",
                file_id=request.files[0].get("id", "unknown") if request.files else "unknown",
                user_id=request.user_id,
                total_passes=request.passes,
                model=getattr(request, 'model', 'gpt-4'),
                metadata={"status": "queued", "progress": 0.0, "current_stage": "queued"}
            )
        
        # Start background task
        task = asyncio.create_task(run_job_background(request, job_id))
        safe_active_tasks_set(job_id, task)
        
        return JSONResponse({"message": "Job queued", "job_id": job_id, "status": "queued"})
    except Exception as e:
        logger.error(f"Failed to queue job: {e}", exc_info=True)
        raise ProcessingError(
            message="Failed to queue job",
            details={"error": str(e)}
        )


@router.post("/{job_id}/cancel")
async def cancel_job(job_id: str) -> JSONResponse:
    """
    Cancel a running job.
    
    Args:
        job_id: Unique job identifier
        
    Returns:
        JSONResponse with cancellation status
        
    Raises:
        NotFoundError: If job is not found
    """
    try:
        task = active_tasks.get(job_id)
        if not task:
            raise NotFoundError("Job not running or not found", job_id)
        
        task.cancel()
        
        # Update job status to cancelled in MongoDB
        if mongodb_db.is_connected():
            mongodb_db.update_job_status(job_id, "cancelled", metadata_update={"current_stage": "cancelled"})
        
        return JSONResponse({"message": "Job cancelled", "job_id": job_id, "status": "cancelled"})
    except NotFoundError:
        raise
    except Exception as e:
        logger.error(f"Failed to cancel job: {e}", exc_info=True)
        raise ProcessingError(
            message="Failed to cancel job",
            details={"job_id": job_id, "error": str(e)}
        )


@router.post("/{job_id}/retry")
async def retry_job(job_id: str, request: RefinementRequest) -> JSONResponse:
    """
    Retry a failed job.
    
    Args:
        job_id: Unique job identifier
        request: Job request data (needed to restart)
        
    Returns:
        JSONResponse with retry status
        
    Raises:
        NotFoundError: If job is not found
    """
    try:
        # Launch a new background run with same effective request
        new_id = str(uuid.uuid4())
        
        # Create retry job in MongoDB
        if mongodb_db.is_connected():
            mongodb_db.create_job(
                job_id=new_id,
                file_name=request.files[0].get("name", "unknown") if request.files else "unknown",
                file_id=request.files[0].get("id", "unknown") if request.files else "unknown",
                user_id=request.user_id,
                total_passes=request.passes,
                model=getattr(request, 'model', 'gpt-4'),
                metadata={"status": "queued", "progress": 0.0, "current_stage": "queued", "retryOf": job_id}
            )
        
        task = asyncio.create_task(run_job_background(request, new_id))
        safe_active_tasks_set(new_id, task)
        
        return JSONResponse({"message": "Job queued for retry", "job_id": new_id, "status": "queued", "retryOf": job_id})
    except Exception as e:
        logger.error(f"Failed to retry job: {e}", exc_info=True)
        raise ProcessingError(
            message="Failed to retry job",
            details={"job_id": job_id, "error": str(e)}
        )


