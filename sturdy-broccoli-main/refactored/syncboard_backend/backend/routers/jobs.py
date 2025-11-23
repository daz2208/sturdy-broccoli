"""
Jobs Router for SyncBoard 3.0 Knowledge Bank - Celery Task Status.

Endpoints:
- GET /jobs/{job_id}/status - Get Celery task status and progress
- DELETE /jobs/{job_id} - Cancel a running task (future enhancement)

Allows frontend to poll for background job progress and results.
"""

import logging
from typing import Dict, Any
from fastapi import APIRouter, HTTPException, Depends
from celery.result import AsyncResult

from ..models import User
from ..dependencies import get_current_user
from ..celery_app import celery_app

# Initialize logger
logger = logging.getLogger(__name__)

# Create router
router = APIRouter(
    prefix="/jobs",
    tags=["jobs"],
    responses={401: {"description": "Unauthorized"}},
)


# =============================================================================
# Job Status Endpoint
# =============================================================================

@router.get("/{job_id}/status")
async def get_job_status(
    job_id: str,
    current_user: User = Depends(get_current_user)
) -> Dict[str, Any]:
    """
    Get Celery task status and progress.

    States:
    - PENDING: Task waiting to be executed
    - PROCESSING: Task is running (with progress metadata)
    - SUCCESS: Task completed successfully
    - FAILURE: Task failed (with error info)
    - RETRY: Task is being retried
    - REVOKED: Task was cancelled

    Args:
        job_id: Celery task ID
        current_user: Authenticated user

    Returns:
        Flat task status dict with status and relevant fields

    Example Response (PROCESSING):
        {
            "job_id": "abc123",
            "status": "PROCESSING",
            "progress": 50,
            "current_step": "Extracting text from PDF"
        }

    Example Response (SUCCESS):
        {
            "job_id": "abc123",
            "status": "SUCCESS",
            "document_id": 42,
            "cluster_id": 5,
            "concepts": [...]
        }

    Example Response (FAILURE):
        {
            "job_id": "abc123",
            "status": "FAILURE",
            "error": "Failed to download URL: 404 Not Found"
        }
    """
    try:
        # Get task result object
        task = AsyncResult(job_id, app=celery_app)

        # Security: Verify job belongs to current user
        # Note: Task metadata should include user_id for ownership check
        if task.state == "SUCCESS" and task.result:
            task_user_id = task.result.get("user_id")
            if task_user_id and task_user_id != current_user.username:
                raise HTTPException(
                    status_code=403,
                    detail="Access denied: This job belongs to another user"
                )

        # Build flat response based on task state
        response = {
            "job_id": job_id,
            "status": task.state
        }

        if task.state == "PENDING":
            # Task hasn't started yet
            response["progress"] = 0
            response["message"] = "Task is waiting in queue..."

        elif task.state == "PROCESSING":
            # Task is running - return progress metadata
            if task.info and isinstance(task.info, dict):
                response["progress"] = task.info.get("progress", 50)
                if "current_step" in task.info:
                    response["current_step"] = task.info["current_step"]
                if "message" in task.info:
                    response["message"] = task.info["message"]
            else:
                response["progress"] = 50
                response["message"] = "Processing..."

        elif task.state == "SUCCESS":
            # Task completed successfully - flatten result into response
            response["progress"] = 100
            if task.result and isinstance(task.result, dict):
                # Copy result fields directly to response
                for key, value in task.result.items():
                    if key != "user_id":  # Don't expose user_id
                        response[key] = value

        elif task.state == "FAILURE":
            # Task failed - return error info
            if isinstance(task.info, dict):
                response["error"] = task.info.get("error", "Unknown error")
            elif task.info:
                response["error"] = str(task.info)
            else:
                response["error"] = "Unknown error"

        elif task.state == "RETRY":
            # Task is being retried
            response["progress"] = 25
            response["message"] = "Task failed, retrying..."
            if task.info and isinstance(task.info, dict):
                if "retry_count" in task.info:
                    response["retry_count"] = task.info["retry_count"]

        elif task.state == "REVOKED":
            # Task was cancelled
            response["progress"] = 0
            response["message"] = "Task was cancelled"

        else:
            # Unknown state
            response["message"] = f"Task state: {task.state}"

        return response

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting job status for {job_id}: {e}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"Failed to get job status: {str(e)}"
        )


# =============================================================================
# Cancel Job Endpoint (Future Enhancement)
# =============================================================================

@router.delete("/{job_id}")
async def cancel_job(
    job_id: str,
    current_user: User = Depends(get_current_user)
) -> Dict[str, str]:
    """
    Cancel a running Celery task.

    Note: This requires celery workers to be started with --pool=gevent or --pool=eventlet
    for proper task revocation. Standard --pool=prefork may not support cancellation.

    Args:
        job_id: Celery task ID
        current_user: Authenticated user

    Returns:
        Success message
    """
    try:
        # Get task
        task = AsyncResult(job_id, app=celery_app)

        # Security: Verify ownership (check if task result has user_id)
        if task.state == "SUCCESS" and task.result:
            task_user_id = task.result.get("user_id")
            if task_user_id and task_user_id != current_user.username:
                raise HTTPException(
                    status_code=403,
                    detail="Access denied: This job belongs to another user"
                )

        # Revoke task
        task.revoke(terminate=True)

        logger.info(f"User {current_user.username} cancelled job {job_id}")

        return {
            "message": f"Job {job_id} has been cancelled",
            "job_id": job_id
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error cancelling job {job_id}: {e}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"Failed to cancel job: {str(e)}"
        )


# =============================================================================
# List User Jobs (Future Enhancement)
# =============================================================================

@router.get("")
async def list_user_jobs(
    current_user: User = Depends(get_current_user),
    limit: int = 10
) -> Dict[str, Any]:
    """
    List recent jobs for current user.

    Note: This requires Redis result backend and task history enabled.
    Currently returns a placeholder - full implementation requires tracking
    user jobs in Redis or database.

    Args:
        current_user: Authenticated user
        limit: Maximum number of jobs to return

    Returns:
        List of recent jobs

    Raises:
        HTTPException 501: Feature not yet implemented
    """
    # Return 501 Not Implemented with clear message
    # Job tracking requires Redis-based implementation (planned feature)
    raise HTTPException(
        status_code=501,
        detail={
            "message": "Job listing feature is not yet implemented",
            "planned_features": [
                "View recent background jobs",
                "Track document processing status",
                "Monitor batch import progress"
            ],
            "workaround": "Use the /admin/chunk-status endpoint for document processing status"
        }
    )
