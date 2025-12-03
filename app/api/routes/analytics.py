"""
Analytics API routes.

This module handles all analytics-related endpoints including usage statistics,
cost tracking, and job metrics.
"""
from __future__ import annotations

import logging
from typing import Dict, Any
from datetime import datetime

from fastapi import APIRouter
from fastapi.responses import JSONResponse

from app.core.mongodb_db import db as mongodb_db
from app.core.exceptions import ProcessingError

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/analytics", tags=["analytics"])


@router.get("/summary")
async def get_analytics_summary() -> JSONResponse:
    """
    Get comprehensive analytics summary, including live OpenAI usage.
    
    Returns:
        JSONResponse with analytics data including:
        - Jobs statistics (total, completed, failed, running)
        - OpenAI usage (requests, tokens, costs)
        - Schema usage statistics
        - Performance metrics
    """
    try:
        logger.debug("Analytics endpoint called")
        
        # Use ONLY MongoDB for analytics
        if not mongodb_db.is_connected():
            return JSONResponse({
                "jobs": {"totalJobs": 0, "completed": 0, "failed": 0, "running": 0, "successRate": 0, "performanceMetrics": {}, "recentActivity": []},
                "openai": {"total_requests": 0, "total_tokens_in": 0, "total_tokens_out": 0, "total_cost": 0.0, "current_model": "gpt-4", "last_24h": {"requests": 0, "tokens_in": 0, "tokens_out": 0, "cost": 0.0, "series": []}},
                "schema_usage": {"total_usages": 0, "most_used_schema": None, "most_used_count": 0, "least_used_schema": None, "least_used_count": 0, "average_usage": 0.0, "schema_usage": {}, "schema_last_used": {}}
            })
        
        # Get all jobs from MongoDB
        jobs = mongodb_db.get_jobs(1000)  # Get last 1000 jobs from MongoDB
        
        # Calculate basic metrics
        total_jobs = len(jobs)
        completed_jobs = [j for j in jobs if j.get("status") == "completed"]
        failed_jobs = [j for j in jobs if j.get("status") == "failed"]
        running_jobs = [j for j in jobs if j.get("status") == "running"]
        
        # Calculate performance metrics
        if completed_jobs:
            # Filter out jobs with missing metrics to avoid skewing averages
            jobs_with_metrics = [j for j in completed_jobs if j.get("metrics")]
            jobs_with_processing_time = [
                j for j in completed_jobs 
                if j.get("metrics", {}).get("processingTime", 0) > 0
            ]
            
            avg_change_percent = sum(
                j.get("metrics", {}).get("changePercent", 0) 
                for j in jobs_with_metrics
            ) / max(len(jobs_with_metrics), 1)
            
            avg_tension_percent = sum(
                j.get("metrics", {}).get("tensionPercent", 0) 
                for j in jobs_with_metrics
            ) / max(len(jobs_with_metrics), 1)
            
            avg_processing_time = sum(
                j.get("metrics", {}).get("processingTime", 0) 
                for j in jobs_with_processing_time
            ) / max(len(jobs_with_processing_time), 1)
            
            avg_risk_reduction = sum(
                j.get("metrics", {}).get("riskReduction", 0) 
                for j in jobs_with_metrics
            ) / max(len(jobs_with_metrics), 1)
        else:
            avg_change_percent = 0
            avg_tension_percent = 0
            avg_processing_time = 0
            avg_risk_reduction = 0
        
        # Recent activity (last 10 jobs) - MongoDB jobs are already sorted by created_at DESC
        recent_activity = jobs[:10]
        
        # Format recent activity for frontend
        formatted_recent_activity = []
        for job in recent_activity:
            job_id = job.get("id", "unknown")
            file_name = job.get("file_name", job.get("fileName", "Unknown"))
            job_status = job.get("status", "unknown")
            
            # Parse created_at - could be ISO string or timestamp
            created_at = job.get("created_at")
            if isinstance(created_at, str):
                timestamp = created_at
            elif isinstance(created_at, (int, float)):
                timestamp = datetime.fromtimestamp(created_at).isoformat()
            else:
                timestamp = datetime.utcnow().isoformat()
            
            formatted_recent_activity.append({
                "id": job_id,
                "fileName": file_name,
                "timestamp": timestamp,
                "status": job_status,
                "action": f"Processing {'completed' if job_status == 'completed' else 'failed' if job_status == 'failed' else 'running' if job_status == 'running' else 'pending'}",
            })
        
        # Get MongoDB analytics
        mongodb_openai = mongodb_db.get_aggregate_analytics()
        mongodb_last_24h = mongodb_db.get_last_24h_analytics()
        
        result: Dict[str, Any] = {
            "jobs": {
                "totalJobs": total_jobs,
                "completed": len(completed_jobs),
                "failed": len(failed_jobs),
                "running": len(running_jobs),
                "successRate": (len(completed_jobs) / total_jobs * 100) if total_jobs > 0 else 0,
                "performanceMetrics": {
                    "avgChangePercent": round(avg_change_percent, 2),
                    "avgTensionPercent": round(avg_tension_percent, 2),
                    "avgProcessingTime": round(avg_processing_time, 2),
                    "avgRiskReduction": round(avg_risk_reduction, 2),
                },
                "recentActivity": formatted_recent_activity
            },
            "openai": {
                **mongodb_openai,
                "last_24h": mongodb_last_24h
            },
            "schema_usage": mongodb_db.get_schema_usage_stats() if mongodb_db.is_connected() else {
                "total_usages": 0,
                "most_used_schema": None,
                "most_used_count": 0,
                "least_used_schema": None,
                "least_used_count": 0,
                "average_usage": 0.0,
                "schema_usage": {},
                "schema_last_used": {}
            }
        }
        
        logger.debug(f"Returning analytics: requests={result['openai']['total_requests']}, cost=${result['openai']['total_cost']:.6f}")
        return JSONResponse(result)
        
    except Exception as e:
        logger.error(f"Analytics summary error: {e}", exc_info=True)
        raise ProcessingError(
            message="Failed to generate analytics summary",
            details={"error": str(e)}
        )


@router.get("/test")
async def test_analytics() -> JSONResponse:
    """
    Test endpoint to verify analytics tracking works.
    
    Returns:
        JSONResponse with test analytics data
    """
    try:
        # Test MongoDB analytics
        if mongodb_db.is_connected():
            # Get current analytics
            analytics = mongodb_db.get_aggregate_analytics()
            return JSONResponse({
                "message": "MongoDB analytics test",
                "mongodb_analytics": analytics,
                "mongodb_connected": True
            })
        else:
            return JSONResponse({
                "message": "MongoDB not connected",
                "mongodb_connected": False
            })
    except Exception as e:
        logger.error(f"Test analytics error: {e}", exc_info=True)
        raise ProcessingError(
            message="Failed to add test analytics",
            details={"error": str(e)}
        )


