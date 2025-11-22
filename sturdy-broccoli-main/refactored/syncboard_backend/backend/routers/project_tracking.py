"""
Project Tracking Router (Phase 10).

Provides endpoints for tracking project attempts, learnings, and statistics.
This data is used to improve future suggestions based on past patterns.
"""

import logging
from fastapi import APIRouter, Depends, HTTPException, Query
from typing import List, Optional
from datetime import datetime
from sqlalchemy import func

from ..models import (
    User, ProjectAttemptCreate, ProjectAttemptUpdate,
    ProjectAttemptResponse, ProjectStatsResponse
)
from ..dependencies import get_current_user
from ..database import get_db_context
from ..db_models import DBProjectAttempt, DBGeneratedCode

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/projects", tags=["project-tracking"])


@router.get("", response_model=List[ProjectAttemptResponse])
async def list_projects(
    status: Optional[str] = Query(None, description="Filter by status"),
    limit: int = Query(50, ge=1, le=100, description="Maximum number of projects to return"),
    offset: int = Query(0, ge=0, description="Number of projects to skip"),
    current_user: User = Depends(get_current_user)
):
    """
    List user's project attempts.

    Can filter by status: 'planned', 'in_progress', 'completed', 'abandoned'
    """
    try:
        with get_db_context() as db:
            query = db.query(DBProjectAttempt).filter(
                DBProjectAttempt.user_id == current_user.username
            )

            if status:
                query = query.filter(DBProjectAttempt.status == status)

            projects = query.order_by(
                DBProjectAttempt.created_at.desc()
            ).offset(offset).limit(limit).all()

            return [ProjectAttemptResponse.model_validate(p) for p in projects]
    except Exception as e:
        logger.error(f"List projects failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/stats", response_model=ProjectStatsResponse)
async def get_project_stats(current_user: User = Depends(get_current_user)):
    """
    Get comprehensive statistics about user's projects.

    Returns:
        - Total projects count
        - Count by status (completed, in_progress, abandoned, planned)
        - Completion rate percentage
        - Average time spent on completed projects
        - Total revenue generated
    """
    try:
        with get_db_context() as db:
            # Total count
            total = db.query(func.count(DBProjectAttempt.id)).filter(
                DBProjectAttempt.user_id == current_user.username
            ).scalar() or 0

            # Count by status
            completed = db.query(func.count(DBProjectAttempt.id)).filter(
                DBProjectAttempt.user_id == current_user.username,
                DBProjectAttempt.status == "completed"
            ).scalar() or 0

            in_progress = db.query(func.count(DBProjectAttempt.id)).filter(
                DBProjectAttempt.user_id == current_user.username,
                DBProjectAttempt.status == "in_progress"
            ).scalar() or 0

            abandoned = db.query(func.count(DBProjectAttempt.id)).filter(
                DBProjectAttempt.user_id == current_user.username,
                DBProjectAttempt.status == "abandoned"
            ).scalar() or 0

            planned = db.query(func.count(DBProjectAttempt.id)).filter(
                DBProjectAttempt.user_id == current_user.username,
                DBProjectAttempt.status == "planned"
            ).scalar() or 0

            # Average time for completed projects
            avg_time = db.query(func.avg(DBProjectAttempt.time_spent_hours)).filter(
                DBProjectAttempt.user_id == current_user.username,
                DBProjectAttempt.status == "completed",
                DBProjectAttempt.time_spent_hours.isnot(None)
            ).scalar()

            # Total revenue
            total_revenue = db.query(func.sum(DBProjectAttempt.revenue_generated)).filter(
                DBProjectAttempt.user_id == current_user.username,
                DBProjectAttempt.revenue_generated.isnot(None)
            ).scalar() or 0.0

            # Calculate completion rate (completed / (completed + abandoned))
            finished_projects = completed + abandoned
            completion_rate = (completed / finished_projects * 100) if finished_projects > 0 else 0.0

            return ProjectStatsResponse(
                total_projects=total,
                completed=completed,
                in_progress=in_progress,
                abandoned=abandoned,
                planned=planned,
                completion_rate=round(completion_rate, 2),
                average_time_hours=round(float(avg_time), 2) if avg_time else 0.0,
                total_revenue=round(float(total_revenue), 2)
            )
    except Exception as e:
        logger.error(f"Get project stats failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/{project_id}", response_model=ProjectAttemptResponse)
async def get_project(
    project_id: int,
    current_user: User = Depends(get_current_user)
):
    """Get a specific project by ID."""
    try:
        with get_db_context() as db:
            project = db.query(DBProjectAttempt).filter(
                DBProjectAttempt.id == project_id,
                DBProjectAttempt.user_id == current_user.username
            ).first()

            if not project:
                raise HTTPException(status_code=404, detail="Project not found")

            return ProjectAttemptResponse.model_validate(project)
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Get project failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("", response_model=ProjectAttemptResponse)
async def create_project(
    project_data: ProjectAttemptCreate,
    current_user: User = Depends(get_current_user)
):
    """
    Create a new project attempt.

    Args:
        project_data: Project creation data including:
            - title: Project name
            - suggestion_id: Optional ID of suggestion that inspired this
            - status: Initial status (default: 'planned')
            - repository_url: Optional GitHub/GitLab URL
            - demo_url: Optional live demo URL
    """
    try:
        with get_db_context() as db:
            db_project = DBProjectAttempt(
                user_id=current_user.username,
                suggestion_id=project_data.suggestion_id,
                title=project_data.title,
                status=project_data.status,
                repository_url=project_data.repository_url,
                demo_url=project_data.demo_url,
                started_at=datetime.utcnow() if project_data.status == "in_progress" else None
            )

            db.add(db_project)
            db.commit()
            db.refresh(db_project)

            logger.info(f"Created project {db_project.id} '{db_project.title}' for user {current_user.username}")
            return ProjectAttemptResponse.model_validate(db_project)
    except Exception as e:
        logger.error(f"Create project failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.put("/{project_id}", response_model=ProjectAttemptResponse)
async def update_project(
    project_id: int,
    update_data: ProjectAttemptUpdate,
    current_user: User = Depends(get_current_user)
):
    """
    Update a project attempt.

    Automatically manages timestamps based on status changes:
    - Setting status to 'in_progress' sets started_at
    - Setting status to 'completed' sets completed_at
    - Setting status to 'abandoned' sets abandoned_at
    """
    try:
        with get_db_context() as db:
            db_project = db.query(DBProjectAttempt).filter(
                DBProjectAttempt.id == project_id,
                DBProjectAttempt.user_id == current_user.username
            ).first()

            if not db_project:
                raise HTTPException(status_code=404, detail="Project not found")

            # Handle status changes with automatic timestamps
            if update_data.status:
                db_project.status = update_data.status
                if update_data.status == "in_progress" and not db_project.started_at:
                    db_project.started_at = datetime.utcnow()
                elif update_data.status == "completed":
                    db_project.completed_at = datetime.utcnow()
                elif update_data.status == "abandoned":
                    db_project.abandoned_at = datetime.utcnow()

            # Update other fields if provided
            if update_data.repository_url is not None:
                db_project.repository_url = update_data.repository_url
            if update_data.demo_url is not None:
                db_project.demo_url = update_data.demo_url
            if update_data.learnings is not None:
                db_project.learnings = update_data.learnings
            if update_data.difficulty_rating is not None:
                db_project.difficulty_rating = update_data.difficulty_rating
            if update_data.time_spent_hours is not None:
                db_project.time_spent_hours = update_data.time_spent_hours
            if update_data.revenue_generated is not None:
                db_project.revenue_generated = update_data.revenue_generated

            db_project.updated_at = datetime.utcnow()

            db.commit()
            db.refresh(db_project)

            logger.info(f"Updated project {project_id} for user {current_user.username}")
            return ProjectAttemptResponse.model_validate(db_project)
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Update project failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/{project_id}")
async def delete_project(
    project_id: int,
    current_user: User = Depends(get_current_user)
):
    """Delete a project attempt and all associated data."""
    try:
        with get_db_context() as db:
            db_project = db.query(DBProjectAttempt).filter(
                DBProjectAttempt.id == project_id,
                DBProjectAttempt.user_id == current_user.username
            ).first()

            if not db_project:
                raise HTTPException(status_code=404, detail="Project not found")

            db.delete(db_project)
            db.commit()

            logger.info(f"Deleted project {project_id} for user {current_user.username}")
            return {"status": "deleted", "project_id": project_id}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Delete project failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/{project_id}/start", response_model=ProjectAttemptResponse)
async def start_project(
    project_id: int,
    current_user: User = Depends(get_current_user)
):
    """Mark a project as started (in_progress)."""
    try:
        with get_db_context() as db:
            db_project = db.query(DBProjectAttempt).filter(
                DBProjectAttempt.id == project_id,
                DBProjectAttempt.user_id == current_user.username
            ).first()

            if not db_project:
                raise HTTPException(status_code=404, detail="Project not found")

            db_project.status = "in_progress"
            db_project.started_at = datetime.utcnow()
            db_project.updated_at = datetime.utcnow()

            db.commit()
            db.refresh(db_project)

            logger.info(f"Started project {project_id} for user {current_user.username}")
            return ProjectAttemptResponse.model_validate(db_project)
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Start project failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/{project_id}/complete", response_model=ProjectAttemptResponse)
async def complete_project(
    project_id: int,
    learnings: Optional[str] = None,
    time_spent_hours: Optional[int] = None,
    difficulty_rating: Optional[int] = None,
    revenue_generated: Optional[float] = None,
    current_user: User = Depends(get_current_user)
):
    """
    Mark a project as completed with optional learnings and metrics.

    This endpoint captures valuable data for improving future suggestions.
    """
    try:
        with get_db_context() as db:
            db_project = db.query(DBProjectAttempt).filter(
                DBProjectAttempt.id == project_id,
                DBProjectAttempt.user_id == current_user.username
            ).first()

            if not db_project:
                raise HTTPException(status_code=404, detail="Project not found")

            db_project.status = "completed"
            db_project.completed_at = datetime.utcnow()
            db_project.updated_at = datetime.utcnow()

            if learnings:
                db_project.learnings = learnings
            if time_spent_hours is not None:
                db_project.time_spent_hours = time_spent_hours
            if difficulty_rating is not None:
                db_project.difficulty_rating = difficulty_rating
            if revenue_generated is not None:
                db_project.revenue_generated = revenue_generated

            db.commit()
            db.refresh(db_project)

            logger.info(f"Completed project {project_id} for user {current_user.username}")
            return ProjectAttemptResponse.model_validate(db_project)
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Complete project failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/{project_id}/abandon", response_model=ProjectAttemptResponse)
async def abandon_project(
    project_id: int,
    learnings: Optional[str] = None,
    time_spent_hours: Optional[int] = None,
    current_user: User = Depends(get_current_user)
):
    """
    Mark a project as abandoned with optional learnings.

    Recording why projects are abandoned helps improve future suggestions
    by avoiding similar patterns.
    """
    try:
        with get_db_context() as db:
            db_project = db.query(DBProjectAttempt).filter(
                DBProjectAttempt.id == project_id,
                DBProjectAttempt.user_id == current_user.username
            ).first()

            if not db_project:
                raise HTTPException(status_code=404, detail="Project not found")

            db_project.status = "abandoned"
            db_project.abandoned_at = datetime.utcnow()
            db_project.updated_at = datetime.utcnow()

            if learnings:
                db_project.learnings = learnings
            if time_spent_hours is not None:
                db_project.time_spent_hours = time_spent_hours

            db.commit()
            db.refresh(db_project)

            logger.info(f"Abandoned project {project_id} for user {current_user.username}")
            return ProjectAttemptResponse.model_validate(db_project)
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Abandon project failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/{project_id}/learnings-summary")
async def get_project_learnings_summary(
    current_user: User = Depends(get_current_user)
):
    """
    Get a summary of learnings from all past projects.

    This is used by the AI to understand user patterns and preferences.
    """
    try:
        with get_db_context() as db:
            # Get completed projects
            completed = db.query(DBProjectAttempt).filter(
                DBProjectAttempt.user_id == current_user.username,
                DBProjectAttempt.status == "completed"
            ).all()

            # Get abandoned projects
            abandoned = db.query(DBProjectAttempt).filter(
                DBProjectAttempt.user_id == current_user.username,
                DBProjectAttempt.status == "abandoned"
            ).all()

            # Build learnings summary
            completed_learnings = []
            for p in completed:
                completed_learnings.append({
                    "title": p.title,
                    "learnings": p.learnings,
                    "time_spent_hours": p.time_spent_hours,
                    "difficulty_rating": p.difficulty_rating,
                    "revenue_generated": p.revenue_generated
                })

            abandoned_learnings = []
            for p in abandoned:
                abandoned_learnings.append({
                    "title": p.title,
                    "learnings": p.learnings,
                    "time_spent_hours": p.time_spent_hours
                })

            # Calculate patterns
            avg_completed_time = sum(
                p.time_spent_hours or 0 for p in completed
            ) / len(completed) if completed else 0

            avg_abandoned_time = sum(
                p.time_spent_hours or 0 for p in abandoned
            ) / len(abandoned) if abandoned else 0

            return {
                "completed_count": len(completed),
                "abandoned_count": len(abandoned),
                "completion_rate": len(completed) / (len(completed) + len(abandoned)) * 100 if (completed or abandoned) else 0,
                "avg_completed_time_hours": round(avg_completed_time, 1),
                "avg_abandoned_time_hours": round(avg_abandoned_time, 1),
                "completed_projects": completed_learnings,
                "abandoned_projects": abandoned_learnings,
                "recommendations": _generate_recommendations(completed, abandoned)
            }
    except Exception as e:
        logger.error(f"Get learnings summary failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


def _generate_recommendations(completed: List[DBProjectAttempt], abandoned: List[DBProjectAttempt]) -> List[str]:
    """Generate recommendations based on project history."""
    recommendations = []

    if not completed and not abandoned:
        recommendations.append("Start your first project to begin tracking progress!")
        return recommendations

    # Check completion rate
    total = len(completed) + len(abandoned)
    if total > 2:
        rate = len(completed) / total
        if rate < 0.3:
            recommendations.append("Consider starting with smaller, more focused projects to improve completion rate")
        elif rate > 0.8:
            recommendations.append("Great completion rate! You might be ready for more challenging projects")

    # Check average time
    if completed:
        avg_time = sum(p.time_spent_hours or 0 for p in completed) / len(completed)
        if avg_time > 40:
            recommendations.append("Your projects average over 40 hours - consider breaking them into smaller milestones")
        elif avg_time < 10:
            recommendations.append("Quick completions! You might benefit from slightly more ambitious projects")

    # Check abandonment patterns
    if len(abandoned) >= 3:
        recommendations.append("Multiple abandoned projects detected - document learnings to improve future success")

    return recommendations
