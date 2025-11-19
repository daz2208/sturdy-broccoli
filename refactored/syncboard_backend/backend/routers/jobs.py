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
        Task status dict with state, meta, and result

    Example Response (PROCESSING):
        {
            "job_id": "abc123",
            "state": "PROCESSING",
            "meta": {
                "stage": "ai_analysis",
                "message": "Running AI concept extraction...",
                "percent": 50
            },
            "result": null
        }

    Example Response (SUCCESS):
        {
            "job_id": "abc123",
            "state": "SUCCESS",
            "meta": {},
            "result": {
                "doc_id": 42,
                "cluster_id": 5,
                "concepts": [...]
            }
        }

    Example Response (FAILURE):
        {
            "job_id": "abc123",
            "state": "FAILURE",
            "meta": {
                "error": "File too large",
                "message": "Failed to process file: File too large"
            },
            "result": null
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

        # Build response based on task state
        response = {
            "job_id": job_id,
            "state": task.state,
            "meta": {},
            "result": None
        }

        if task.state == "PENDING":
            # Task hasn't started yet
            response["meta"] = {
                "message": "Task is waiting in queue...",
                "percent": 0
            }

        elif task.state == "PROCESSING":
            # Task is running - return progress metadata
            response["meta"] = task.info or {
                "message": "Processing...",
                "percent": 50
            }

        elif task.state == "SUCCESS":
            # Task completed successfully
            response["result"] = task.result
            response["meta"] = {
                "message": "Task completed successfully",
                "percent": 100
            }

        elif task.state == "FAILURE":
            # Task failed - return error info
            response["meta"] = task.info or {
                "error": "Unknown error",
                "message": "Task failed"
            }
            # Don't expose full exception traceback to client
            if isinstance(task.info, dict):
                response["meta"]["error"] = task.info.get("error", "Unknown error")
            else:
                response["meta"]["error"] = str(task.info)

        elif task.state == "RETRY":
            # Task is being retried
            response["meta"] = {
                "message": "Task failed, retrying...",
                "percent": 25
            }

        elif task.state == "REVOKED":
            # Task was cancelled
            response["meta"] = {
                "message": "Task was cancelled",
                "percent": 0
            }

        else:
            # Unknown state
            response["meta"] = {
                "message": f"Task state: {task.state}",
                "percent": 0
            }

        return response

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
    """
    # TODO: Implement job tracking in Redis
    # For now, return placeholder
    return {
        "message": "Job listing not yet implemented",
        "user": current_user.username,
        "jobs": []
    }
