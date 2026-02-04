"""
Jobs API routes.

This module handles job management endpoints including job listing, status checking,
queueing, cancellation, and retry operations.
"""
from __future__ import annotations

import logging
import os
from typing import Dict, Any, Optional

from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import JSONResponse

from app.core.mongodb_db import db as mongodb_db
from app.core.exceptions import NotFoundError, ProcessingError
from app.api.routes.refine import run_job_background, RefinementRequest
from app.core.state import active_tasks, safe_active_tasks_set
from app.services.export_service import export_refined_document, _get_final_text_and_path
from app.core.database import get_job
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
        
        # Get job from MongoDB (with connection check)
        if mongodb_db.is_connected():
            jobs = mongodb_db.get_jobs(1)
            job = next((j for j in jobs if j.get("id") == job_id), None)
        else:
            job = None
        
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


@router.get("/{job_id}/export")
async def export_job(job_id: str, format: str = "same") -> JSONResponse:
    """
    Export the final refined document for a job in a specific format.

    The response is always structured as:
    {
      "status": "success | partial_success | error",
      "format": "pdf | docx | txt | null",
      "download_url": "...",
      "warnings": [...]
    }
    """
    try:
        payload = export_refined_document(job_id, export_format=format)

        status = payload.get("status") or "error"
        if status == "error":
            # Use 400 for contract-level errors; 404 is encoded in warnings
            return JSONResponse(payload, status_code=400)

        return JSONResponse(payload)
    except Exception as e:
        logger.error(f"Failed to export job {job_id}: {e}", exc_info=True)
        return JSONResponse(
            {
                "status": "error",
                "format": None,
                "download_url": None,
                "warnings": ["unexpected_export_error"],
            },
            status_code=500,
        )


@router.get("/{job_id}/export_pass")
async def export_job_pass(
    job_id: str,
    file_id: str = Query(..., description="File ID"),
    pass_number: int = Query(..., description="Pass number to export", alias="pass"),
    format: str = Query("same", description="Export format (same, pdf, docx, txt)")
) -> JSONResponse:
    """
    Export a specific pass from a job's refinement process.
    
    Args:
        job_id: Job identifier
        file_id: File identifier
        pass_number: Pass number (1-based)
        format: Export format (same, pdf, docx, txt)
    
    Returns:
        JSONResponse with export status and download URL
    """
    try:
        logger.info(f"Exporting pass {pass_number} for job {job_id}, file {file_id}, format {format}")
        
        # Use export_refined_document with file_id and pass_number
        payload = export_refined_document(
            job_id=job_id,
            export_format=format,
            file_id=file_id,
            pass_number=pass_number
        )

        status = payload.get("status") or "error"
        if status == "error":
            return JSONResponse(payload, status_code=400)

        return JSONResponse(payload)
    except Exception as e:
        logger.error(f"Failed to export pass {pass_number} for job {job_id}: {e}", exc_info=True)
        return JSONResponse(
            {
                "status": "error",
                "format": None,
                "download_url": None,
                "warnings": ["unexpected_export_error", str(e)],
            },
            status_code=500,
        )


@router.post("/{job_id}/export/google-doc")
async def export_job_to_google_docs(
    job_id: str,
    folder_id: Optional[str] = Query(None, description="Google Drive folder ID (defaults to 'root')")
) -> JSONResponse:
    """
    Export the refined document as a Google Doc.
    
    This endpoint:
    1. Retrieves the refined text from the completed job
    2. Creates a new Google Doc with the refined content
    3. Optionally places it in a specific Google Drive folder
    4. Returns the document ID and URL for immediate access
    
    Args:
        job_id: Unique job identifier
        folder_id: Optional Google Drive folder ID. If not provided or "root", 
                   the document is created in the root of My Drive.
    
    Returns:
        JSONResponse with structure:
        {
          "status": "success | partial_success | error",
          "doc_id": "...",
          "doc_url": "https://docs.google.com/document/d/...",
          "title": "document_name",
          "warnings": [...]
        }
    
    Raises:
        HTTPException: If Google credentials are not configured or invalid
    """
    warnings = []
    
    try:
        # 1. Get job and refined text
        job = get_job(job_id)
        if not job or not getattr(job, "result", None):
            return JSONResponse(
                {
                    "status": "error",
                    "doc_id": None,
                    "doc_url": None,
                    "title": None,
                    "warnings": ["job_not_found_or_no_result"],
                    "error": "Job not found or not completed"
                },
                status_code=404
            )
        
        job_result = job.result or {}
        refined_text, _, text_warnings = _get_final_text_and_path(job_result)
        warnings.extend(text_warnings)
        
        if not refined_text or not refined_text.strip():
            return JSONResponse(
                {
                    "status": "error",
                    "doc_id": None,
                    "doc_url": None,
                    "title": None,
                    "warnings": warnings + ["no_refined_text_available"],
                    "error": "No refined text available to export"
                },
                status_code=400
            )
        
        # 2. Determine document title from original file
        original_path = job_result.get("original_file_path", "")
        if original_path:
            base_name = os.path.splitext(os.path.basename(str(original_path)))[0]
            title = f"{base_name} (refined)"
        else:
            title = f"Refined Document {job_id[:8]}"
        
        # 3. Import Google utilities
        try:
            from app.utils.utils import create_google_doc, get_drive_service, get_google_credentials
        except ImportError as e:
            logger.error(f"Failed to import Google utilities: {e}")
            return JSONResponse(
                {
                    "status": "error",
                    "doc_id": None,
                    "doc_url": None,
                    "title": None,
                    "warnings": ["google_utils_import_error"],
                    "error": "Google Drive integration not properly configured"
                },
                status_code=500
            )
        
        # 4. Check Google credentials
        creds = get_google_credentials()
        if not creds:
            return JSONResponse(
                {
                    "status": "error",
                    "doc_id": None,
                    "doc_url": None,
                    "title": None,
                    "warnings": ["google_credentials_not_configured"],
                    "error": "Google Drive credentials not configured. Please set GOOGLE_SERVICE_ACCOUNT_JSON or GOOGLE_SERVICE_ACCOUNT_FILE in environment."
                },
                status_code=503
            )
        
        # 5. Create Google Doc
        logger.info(f"Creating Google Doc for job {job_id} with title: {title}")
        try:
            doc_id = create_google_doc(title, refined_text)
        except Exception as e:
            logger.error(f"Failed to create Google Doc: {e}", exc_info=True)
            error_msg = str(e)
            
            # Provide helpful error messages
            if "invalid_grant" in error_msg.lower() or "jwt" in error_msg.lower():
                error_msg = "Google credentials are invalid or expired. Please regenerate the service account key."
                warnings.append("invalid_google_credentials")
            elif "permission" in error_msg.lower() or "forbidden" in error_msg.lower():
                error_msg = "Insufficient permissions to create Google Docs. Check service account permissions."
                warnings.append("insufficient_permissions")
            else:
                warnings.append("google_doc_creation_failed")
            
            return JSONResponse(
                {
                    "status": "error",
                    "doc_id": None,
                    "doc_url": None,
                    "title": title,
                    "warnings": warnings,
                    "error": error_msg
                },
                status_code=500
            )
        
        # 6. Optionally move to specific folder
        if folder_id and folder_id != "root":
            try:
                drive_service = get_drive_service()
                if drive_service:
                    # Move the document to the specified folder
                    drive_service.files().update(
                        fileId=doc_id,
                        addParents=folder_id,
                        removeParents='root',
                        fields='id, parents'
                    ).execute()
                    logger.info(f"Moved document {doc_id} to folder {folder_id}")
                else:
                    warnings.append("could_not_move_to_folder_no_service")
            except Exception as e:
                logger.warning(f"Failed to move document to folder {folder_id}: {e}")
                warnings.append("could_not_move_to_folder")
                # Don't fail the entire operation if folder move fails
        
        # 7. Generate document URL
        doc_url = f"https://docs.google.com/document/d/{doc_id}/edit"
        
        logger.info(f"Successfully exported job {job_id} to Google Doc {doc_id}")
        
        return JSONResponse(
            {
                "status": "success" if not warnings else "partial_success",
                "doc_id": doc_id,
                "doc_url": doc_url,
                "title": title,
                "warnings": warnings
            },
            status_code=200
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Unexpected error exporting job {job_id} to Google Docs: {e}", exc_info=True)
        return JSONResponse(
            {
                "status": "error",
                "doc_id": None,
                "doc_url": None,
                "title": None,
                "warnings": warnings + ["unexpected_export_error"],
                "error": f"Unexpected error: {str(e)}"
            },
            status_code=500
        )

