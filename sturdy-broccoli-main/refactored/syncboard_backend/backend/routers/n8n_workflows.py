"""
n8n Workflow Generation Router (Phase 10).

Provides endpoints for generating, storing, and managing n8n automation workflows.
Uses AI to generate complete, importable n8n workflow JSON from task descriptions.
"""

import logging
import os
from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import JSONResponse
from typing import List, Optional
from datetime import datetime

from ..models import User, N8nGenerationRequest, N8nWorkflowResponse, N8nWorkflowUpdate
from ..dependencies import get_current_user, get_kb_metadata, get_kb_documents
from ..database import get_db_context
from ..db_models import DBN8nWorkflow, DBDocument

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/n8n-workflows", tags=["n8n"])


@router.post("/generate")
async def generate_workflow(
    req: N8nGenerationRequest,
    current_user: User = Depends(get_current_user)
):
    """
    Generate an n8n workflow from task description.

    Uses AI to create a complete n8n workflow JSON that can be directly
    imported into n8n. The workflow is stored for future reference.

    Args:
        req: Generation request with:
            - task_description: What the workflow should do
            - available_integrations: Optional list of services user has access to

    Returns:
        Generated workflow with setup instructions
    """
    try:
        # Import LLM provider
        from ..llm_providers import OpenAIProvider

        # Get user's knowledge for context
        from ..dependencies import get_user_default_kb_id

        with get_db_context() as db:
            # Build knowledge summary from user's documents
            knowledge_summary = ""
            try:
                kb_id = get_user_default_kb_id(current_user.username, db)
                kb_metadata = get_kb_metadata(kb_id)
                kb_documents = get_kb_documents(kb_id)

                user_docs = [
                    (did, doc) for did, doc in kb_documents.items()
                    if kb_metadata.get(did) and kb_metadata[did].owner == current_user.username
                ]
                for doc_id, content in user_docs[:5]:
                    meta = kb_metadata[doc_id]
                    knowledge_summary += f"\n{meta.filename or 'Document'}: {content[:500]}...\n"
            except Exception as e:
                logger.warning(f"Could not load user knowledge: {e}")
                knowledge_summary = ""

            # Find any existing n8n workflows in user's docs for reference
            user_examples = []
            existing_workflows = db.query(DBN8nWorkflow).filter(
                DBN8nWorkflow.user_id == current_user.username
            ).limit(3).all()
            for w in existing_workflows:
                user_examples.append({
                    'name': w.title,
                    'description': w.description,
                    'nodes': list(w.workflow_json.get('nodes', [])) if isinstance(w.workflow_json, dict) else []
                })

            # Initialize LLM provider
            api_key = os.getenv("OPENAI_API_KEY")
            if not api_key:
                raise HTTPException(status_code=503, detail="OpenAI API key not configured")

            provider = OpenAIProvider(
                api_key=api_key,
                suggestion_model="gpt-4o"
            )

            # Generate workflow
            result = await provider.generate_n8n_workflow(
                task_description=req.task_description,
                knowledge_summary=knowledge_summary,
                available_integrations=req.available_integrations or [],
                user_examples=user_examples
            )

            if result.get('error'):
                raise HTTPException(status_code=500, detail=result['error'])

            workflow = result.get('workflow', {})

            # Save to database
            db_workflow = DBN8nWorkflow(
                user_id=current_user.username,
                title=workflow.get('name', 'Generated Workflow'),
                description=result.get('workflow_description', req.task_description),
                workflow_json=workflow,
                task_description=req.task_description,
                required_integrations=req.available_integrations,
                trigger_type=result.get('trigger_type', 'unknown'),
                estimated_complexity=result.get('complexity', 'medium')
            )

            db.add(db_workflow)
            db.commit()
            db.refresh(db_workflow)

            logger.info(f"Generated n8n workflow {db_workflow.id} for user {current_user.username}")

            return {
                "workflow_id": db_workflow.id,
                "workflow": workflow,
                "setup_instructions": result.get('setup_instructions', ''),
                "required_credentials": result.get('required_credentials', []),
                "testing_steps": result.get('testing_steps', []),
                "potential_improvements": result.get('potential_improvements', []),
                "download_url": f"/n8n-workflows/{db_workflow.id}/download"
            }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Generate workflow failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("", response_model=List[N8nWorkflowResponse])
async def list_workflows(
    limit: int = Query(50, ge=1, le=100),
    offset: int = Query(0, ge=0),
    current_user: User = Depends(get_current_user)
):
    """List user's generated n8n workflows."""
    try:
        with get_db_context() as db:
            workflows = db.query(DBN8nWorkflow).filter(
                DBN8nWorkflow.user_id == current_user.username
            ).order_by(DBN8nWorkflow.created_at.desc()).offset(offset).limit(limit).all()

            return [N8nWorkflowResponse.model_validate(w) for w in workflows]
    except Exception as e:
        logger.error(f"List workflows failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/{workflow_id}", response_model=N8nWorkflowResponse)
async def get_workflow(
    workflow_id: int,
    current_user: User = Depends(get_current_user)
):
    """Get a specific workflow by ID."""
    try:
        with get_db_context() as db:
            workflow = db.query(DBN8nWorkflow).filter(
                DBN8nWorkflow.id == workflow_id,
                DBN8nWorkflow.user_id == current_user.username
            ).first()

            if not workflow:
                raise HTTPException(status_code=404, detail="Workflow not found")

            return N8nWorkflowResponse.model_validate(workflow)
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Get workflow failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/{workflow_id}/download")
async def download_workflow(
    workflow_id: int,
    current_user: User = Depends(get_current_user)
):
    """
    Download n8n workflow JSON file.

    Returns the workflow in a format that can be directly imported into n8n.
    """
    try:
        with get_db_context() as db:
            workflow = db.query(DBN8nWorkflow).filter(
                DBN8nWorkflow.id == workflow_id,
                DBN8nWorkflow.user_id == current_user.username
            ).first()

            if not workflow:
                raise HTTPException(status_code=404, detail="Workflow not found")

            # Create filename from title
            filename = workflow.title.replace(' ', '_').replace('/', '_')[:50] + '.json'

            return JSONResponse(
                content=workflow.workflow_json,
                headers={
                    "Content-Disposition": f"attachment; filename={filename}"
                }
            )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Download workflow failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.put("/{workflow_id}", response_model=N8nWorkflowResponse)
async def update_workflow(
    workflow_id: int,
    update_data: N8nWorkflowUpdate,
    current_user: User = Depends(get_current_user)
):
    """
    Update workflow metadata (tested/deployed status).

    Use this to track which workflows have been tested and deployed.
    """
    try:
        with get_db_context() as db:
            workflow = db.query(DBN8nWorkflow).filter(
                DBN8nWorkflow.id == workflow_id,
                DBN8nWorkflow.user_id == current_user.username
            ).first()

            if not workflow:
                raise HTTPException(status_code=404, detail="Workflow not found")

            if update_data.tested is not None:
                workflow.tested = update_data.tested
            if update_data.deployed is not None:
                workflow.deployed = update_data.deployed

            workflow.updated_at = datetime.utcnow()

            db.commit()
            db.refresh(workflow)

            logger.info(f"Updated workflow {workflow_id} for user {current_user.username}")
            return N8nWorkflowResponse.model_validate(workflow)
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Update workflow failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/{workflow_id}")
async def delete_workflow(
    workflow_id: int,
    current_user: User = Depends(get_current_user)
):
    """Delete a workflow."""
    try:
        with get_db_context() as db:
            workflow = db.query(DBN8nWorkflow).filter(
                DBN8nWorkflow.id == workflow_id,
                DBN8nWorkflow.user_id == current_user.username
            ).first()

            if not workflow:
                raise HTTPException(status_code=404, detail="Workflow not found")

            db.delete(workflow)
            db.commit()

            logger.info(f"Deleted workflow {workflow_id} for user {current_user.username}")
            return {"status": "deleted", "workflow_id": workflow_id}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Delete workflow failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/{workflow_id}/duplicate", response_model=N8nWorkflowResponse)
async def duplicate_workflow(
    workflow_id: int,
    current_user: User = Depends(get_current_user)
):
    """Create a copy of an existing workflow."""
    try:
        with get_db_context() as db:
            original = db.query(DBN8nWorkflow).filter(
                DBN8nWorkflow.id == workflow_id,
                DBN8nWorkflow.user_id == current_user.username
            ).first()

            if not original:
                raise HTTPException(status_code=404, detail="Workflow not found")

            # Create copy
            new_workflow = DBN8nWorkflow(
                user_id=current_user.username,
                title=f"{original.title} (Copy)",
                description=original.description,
                workflow_json=original.workflow_json,
                task_description=original.task_description,
                required_integrations=original.required_integrations,
                trigger_type=original.trigger_type,
                estimated_complexity=original.estimated_complexity,
                tested=False,
                deployed=False
            )

            db.add(new_workflow)
            db.commit()
            db.refresh(new_workflow)

            logger.info(f"Duplicated workflow {workflow_id} to {new_workflow.id}")
            return N8nWorkflowResponse.model_validate(new_workflow)
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Duplicate workflow failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))
