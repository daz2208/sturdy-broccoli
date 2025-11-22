"""
Project Goals Router (Phase 10).

Provides endpoints for managing user project goals and constraints
for personalized AI-driven build suggestions.
"""

import logging
from fastapi import APIRouter, Depends, HTTPException
from typing import List
from datetime import datetime

from ..models import User, ProjectGoalCreate, ProjectGoalUpdate, ProjectGoalResponse
from ..dependencies import get_current_user
from ..database import get_db_context
from ..db_models import DBProjectGoal

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/project-goals", tags=["project-goals"])


@router.get("", response_model=List[ProjectGoalResponse])
async def get_user_goals(current_user: User = Depends(get_current_user)):
    """
    Get all project goals for the current user.

    Returns goals sorted by priority (highest first).
    """
    try:
        with get_db_context() as db:
            goals = db.query(DBProjectGoal).filter(
                DBProjectGoal.user_id == current_user.username
            ).order_by(DBProjectGoal.priority.desc()).all()

            return [ProjectGoalResponse.model_validate(g) for g in goals]
    except Exception as e:
        logger.error(f"Get user goals failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/primary", response_model=ProjectGoalResponse)
async def get_primary_goal(current_user: User = Depends(get_current_user)):
    """
    Get the user's primary (highest priority) goal.

    Returns the goal with highest priority, or creates a default if none exists.
    """
    try:
        with get_db_context() as db:
            goal = db.query(DBProjectGoal).filter(
                DBProjectGoal.user_id == current_user.username
            ).order_by(DBProjectGoal.priority.desc()).first()

            if not goal:
                # Create default goal
                goal = DBProjectGoal(
                    user_id=current_user.username,
                    goal_type='revenue',
                    priority=0,
                    constraints={
                        'time_available': 'weekends',
                        'budget': 0,
                        'target_market': 'B2B SaaS',
                        'tech_stack_preference': 'Python/FastAPI',
                        'deployment_preference': 'Docker'
                    }
                )
                db.add(goal)
                db.commit()
                db.refresh(goal)

            return ProjectGoalResponse.model_validate(goal)
    except Exception as e:
        logger.error(f"Get primary goal failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/{goal_id}", response_model=ProjectGoalResponse)
async def get_goal(
    goal_id: int,
    current_user: User = Depends(get_current_user)
):
    """Get a specific project goal by ID."""
    try:
        with get_db_context() as db:
            goal = db.query(DBProjectGoal).filter(
                DBProjectGoal.id == goal_id,
                DBProjectGoal.user_id == current_user.username
            ).first()

            if not goal:
                raise HTTPException(status_code=404, detail="Goal not found")

            return ProjectGoalResponse.model_validate(goal)
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Get goal failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("", response_model=ProjectGoalResponse)
async def create_goal(
    goal_data: ProjectGoalCreate,
    current_user: User = Depends(get_current_user)
):
    """
    Create a new project goal.

    Args:
        goal_data: Goal creation data including:
            - goal_type: 'revenue', 'learning', 'portfolio', 'automation'
            - priority: Higher numbers = higher priority
            - constraints: Dict with time_available, budget, target_market, etc.

    Returns:
        Created goal object
    """
    try:
        with get_db_context() as db:
            # Create the goal
            db_goal = DBProjectGoal(
                user_id=current_user.username,
                goal_type=goal_data.goal_type,
                priority=goal_data.priority,
                constraints=goal_data.constraints or {}
            )

            db.add(db_goal)
            db.commit()
            db.refresh(db_goal)

            logger.info(f"Created project goal {db_goal.id} for user {current_user.username}")
            return ProjectGoalResponse.model_validate(db_goal)
    except Exception as e:
        logger.error(f"Create goal failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.put("/{goal_id}", response_model=ProjectGoalResponse)
async def update_goal(
    goal_id: int,
    goal_data: ProjectGoalUpdate,
    current_user: User = Depends(get_current_user)
):
    """
    Update an existing project goal.

    Only updates fields that are provided (non-None).
    """
    try:
        with get_db_context() as db:
            db_goal = db.query(DBProjectGoal).filter(
                DBProjectGoal.id == goal_id,
                DBProjectGoal.user_id == current_user.username
            ).first()

            if not db_goal:
                raise HTTPException(status_code=404, detail="Goal not found")

            # Update only provided fields
            if goal_data.goal_type is not None:
                db_goal.goal_type = goal_data.goal_type
            if goal_data.priority is not None:
                db_goal.priority = goal_data.priority
            if goal_data.constraints is not None:
                db_goal.constraints = goal_data.constraints

            db_goal.updated_at = datetime.utcnow()

            db.commit()
            db.refresh(db_goal)

            logger.info(f"Updated project goal {goal_id} for user {current_user.username}")
            return ProjectGoalResponse.model_validate(db_goal)
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Update goal failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/{goal_id}")
async def delete_goal(
    goal_id: int,
    current_user: User = Depends(get_current_user)
):
    """Delete a project goal."""
    try:
        with get_db_context() as db:
            db_goal = db.query(DBProjectGoal).filter(
                DBProjectGoal.id == goal_id,
                DBProjectGoal.user_id == current_user.username
            ).first()

            if not db_goal:
                raise HTTPException(status_code=404, detail="Goal not found")

            db.delete(db_goal)
            db.commit()

            logger.info(f"Deleted project goal {goal_id} for user {current_user.username}")
            return {"status": "deleted", "goal_id": goal_id}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Delete goal failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/set-primary/{goal_id}", response_model=ProjectGoalResponse)
async def set_primary_goal(
    goal_id: int,
    current_user: User = Depends(get_current_user)
):
    """
    Set a goal as the primary (highest priority) goal.

    This increases the specified goal's priority to be higher than all others.
    """
    try:
        with get_db_context() as db:
            db_goal = db.query(DBProjectGoal).filter(
                DBProjectGoal.id == goal_id,
                DBProjectGoal.user_id == current_user.username
            ).first()

            if not db_goal:
                raise HTTPException(status_code=404, detail="Goal not found")

            # Find the highest current priority
            max_priority = db.query(DBProjectGoal).filter(
                DBProjectGoal.user_id == current_user.username
            ).order_by(DBProjectGoal.priority.desc()).first()

            # Set this goal's priority higher
            new_priority = (max_priority.priority + 1) if max_priority else 1
            db_goal.priority = new_priority
            db_goal.updated_at = datetime.utcnow()

            db.commit()
            db.refresh(db_goal)

            logger.info(f"Set goal {goal_id} as primary for user {current_user.username}")
            return ProjectGoalResponse.model_validate(db_goal)
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Set primary goal failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))
