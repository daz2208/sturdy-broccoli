"""
Generated Code Router (Phase 10).

Provides endpoints for managing generated code files, including storage,
retrieval, and ZIP downloads for complete projects.
"""

import logging
import io
import zipfile
from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import PlainTextResponse, StreamingResponse
from typing import List, Optional
from datetime import datetime

from ..models import User, GeneratedCodeResponse
from ..dependencies import get_current_user
from ..database import get_db_context
from ..db_models import DBGeneratedCode, DBProjectAttempt

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/generated-code", tags=["generated-code"])


@router.get("", response_model=List[GeneratedCodeResponse])
async def list_generated_code(
    project_id: Optional[int] = Query(None, description="Filter by project ID"),
    language: Optional[str] = Query(None, description="Filter by language"),
    generation_type: Optional[str] = Query(None, description="Filter by type"),
    limit: int = Query(50, ge=1, le=100),
    offset: int = Query(0, ge=0),
    current_user: User = Depends(get_current_user)
):
    """
    List generated code files.

    Can filter by project, language, or generation type.
    """
    try:
        with get_db_context() as db:
            query = db.query(DBGeneratedCode).filter(
                DBGeneratedCode.user_id == current_user.username
            )

            if project_id:
                query = query.filter(DBGeneratedCode.project_attempt_id == project_id)
            if language:
                query = query.filter(DBGeneratedCode.language == language)
            if generation_type:
                query = query.filter(DBGeneratedCode.generation_type == generation_type)

            code_files = query.order_by(
                DBGeneratedCode.created_at.desc()
            ).offset(offset).limit(limit).all()

            return [GeneratedCodeResponse.model_validate(c) for c in code_files]
    except Exception as e:
        logger.error(f"List generated code failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/{code_id}", response_model=GeneratedCodeResponse)
async def get_code(
    code_id: int,
    current_user: User = Depends(get_current_user)
):
    """Get a specific code file by ID."""
    try:
        with get_db_context() as db:
            code = db.query(DBGeneratedCode).filter(
                DBGeneratedCode.id == code_id,
                DBGeneratedCode.user_id == current_user.username
            ).first()

            if not code:
                raise HTTPException(status_code=404, detail="Code file not found")

            return GeneratedCodeResponse.model_validate(code)
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Get code failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/{code_id}/download")
async def download_code(
    code_id: int,
    current_user: User = Depends(get_current_user)
):
    """Download a generated code file."""
    try:
        with get_db_context() as db:
            code = db.query(DBGeneratedCode).filter(
                DBGeneratedCode.id == code_id,
                DBGeneratedCode.user_id == current_user.username
            ).first()

            if not code:
                raise HTTPException(status_code=404, detail="Code file not found")

            filename = code.filename or f"generated_code.{code.language or 'txt'}"

            return PlainTextResponse(
                content=code.code_content,
                headers={
                    "Content-Disposition": f"attachment; filename={filename}"
                }
            )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Download code failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/project/{project_id}/files", response_model=List[GeneratedCodeResponse])
async def get_project_files(
    project_id: int,
    current_user: User = Depends(get_current_user)
):
    """Get all code files for a specific project."""
    try:
        with get_db_context() as db:
            # Verify project belongs to user
            project = db.query(DBProjectAttempt).filter(
                DBProjectAttempt.id == project_id,
                DBProjectAttempt.user_id == current_user.username
            ).first()

            if not project:
                raise HTTPException(status_code=404, detail="Project not found")

            code_files = db.query(DBGeneratedCode).filter(
                DBGeneratedCode.project_attempt_id == project_id,
                DBGeneratedCode.user_id == current_user.username
            ).order_by(DBGeneratedCode.filename).all()

            return [GeneratedCodeResponse.model_validate(c) for c in code_files]
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Get project files failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/project/{project_id}/zip")
async def download_project_zip(
    project_id: int,
    current_user: User = Depends(get_current_user)
):
    """
    Download all code files for a project as a ZIP archive.

    Includes a README.md with setup instructions if available.
    """
    try:
        with get_db_context() as db:
            # Verify project belongs to user
            project = db.query(DBProjectAttempt).filter(
                DBProjectAttempt.id == project_id,
                DBProjectAttempt.user_id == current_user.username
            ).first()

            if not project:
                raise HTTPException(status_code=404, detail="Project not found")

            code_files = db.query(DBGeneratedCode).filter(
                DBGeneratedCode.project_attempt_id == project_id,
                DBGeneratedCode.user_id == current_user.username
            ).all()

            if not code_files:
                raise HTTPException(status_code=404, detail="No code files found for this project")

            # Create ZIP in memory
            zip_buffer = io.BytesIO()
            with zipfile.ZipFile(zip_buffer, 'w', zipfile.ZIP_DEFLATED) as zip_file:
                # Add all code files
                for code in code_files:
                    filename = code.filename or f"file_{code.id}.{code.language or 'txt'}"
                    zip_file.writestr(filename, code.code_content)

                # Add README with setup instructions
                readme_content = _generate_readme(project, code_files)
                zip_file.writestr("README.md", readme_content)

            zip_buffer.seek(0)

            # Create safe filename
            project_name = project.title.replace(' ', '_').replace('/', '_')[:30]
            zip_filename = f"{project_name}_project_{project_id}.zip"

            return StreamingResponse(
                io.BytesIO(zip_buffer.read()),
                media_type="application/zip",
                headers={
                    "Content-Disposition": f"attachment; filename={zip_filename}"
                }
            )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Download project ZIP failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/{code_id}")
async def delete_code(
    code_id: int,
    current_user: User = Depends(get_current_user)
):
    """Delete a generated code file."""
    try:
        with get_db_context() as db:
            code = db.query(DBGeneratedCode).filter(
                DBGeneratedCode.id == code_id,
                DBGeneratedCode.user_id == current_user.username
            ).first()

            if not code:
                raise HTTPException(status_code=404, detail="Code file not found")

            db.delete(code)
            db.commit()

            logger.info(f"Deleted code file {code_id} for user {current_user.username}")
            return {"status": "deleted", "code_id": code_id}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Delete code failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/store")
async def store_code(
    project_id: Optional[int] = None,
    generation_type: str = "script",
    language: str = "python",
    filename: str = "generated.py",
    code_content: str = "",
    description: Optional[str] = None,
    dependencies: Optional[List[str]] = None,
    setup_instructions: Optional[str] = None,
    current_user: User = Depends(get_current_user)
):
    """
    Store a generated code file.

    This endpoint is used internally by the build suggestion system
    to store generated starter code.
    """
    try:
        with get_db_context() as db:
            # Verify project if provided
            if project_id:
                project = db.query(DBProjectAttempt).filter(
                    DBProjectAttempt.id == project_id,
                    DBProjectAttempt.user_id == current_user.username
                ).first()
                if not project:
                    raise HTTPException(status_code=404, detail="Project not found")

            db_code = DBGeneratedCode(
                user_id=current_user.username,
                project_attempt_id=project_id,
                generation_type=generation_type,
                language=language,
                filename=filename,
                code_content=code_content,
                description=description,
                dependencies=dependencies,
                setup_instructions=setup_instructions
            )

            db.add(db_code)
            db.commit()
            db.refresh(db_code)

            logger.info(f"Stored code file {db_code.id} for user {current_user.username}")
            return GeneratedCodeResponse.model_validate(db_code)
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Store code failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/store-batch")
async def store_code_batch(
    project_id: int,
    files: dict,
    current_user: User = Depends(get_current_user)
):
    """
    Store multiple code files at once.

    Args:
        project_id: Project to associate files with
        files: Dict mapping filename to content, e.g.:
            {
                "main.py": "code content...",
                "models.py": "code content...",
                "requirements.txt": "fastapi\\nuvicorn"
            }
    """
    try:
        with get_db_context() as db:
            # Verify project
            project = db.query(DBProjectAttempt).filter(
                DBProjectAttempt.id == project_id,
                DBProjectAttempt.user_id == current_user.username
            ).first()
            if not project:
                raise HTTPException(status_code=404, detail="Project not found")

            stored_files = []
            for filename, content in files.items():
                # Detect language from extension
                language = _detect_language(filename)

                db_code = DBGeneratedCode(
                    user_id=current_user.username,
                    project_attempt_id=project_id,
                    generation_type="starter_project",
                    language=language,
                    filename=filename,
                    code_content=content
                )
                db.add(db_code)
                stored_files.append(filename)

            db.commit()

            logger.info(f"Stored {len(stored_files)} files for project {project_id}")
            return {
                "status": "success",
                "files_stored": len(stored_files),
                "filenames": stored_files
            }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Store code batch failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


def _detect_language(filename: str) -> str:
    """Detect programming language from filename extension."""
    extension_map = {
        '.py': 'python',
        '.js': 'javascript',
        '.ts': 'typescript',
        '.jsx': 'javascript',
        '.tsx': 'typescript',
        '.json': 'json',
        '.yml': 'yaml',
        '.yaml': 'yaml',
        '.md': 'markdown',
        '.html': 'html',
        '.css': 'css',
        '.sql': 'sql',
        '.sh': 'bash',
        '.bash': 'bash',
        '.dockerfile': 'dockerfile',
        '.go': 'go',
        '.rs': 'rust',
        '.java': 'java',
        '.rb': 'ruby',
        '.php': 'php',
        '.txt': 'text',
        '.env': 'env',
        '.example': 'text'
    }

    # Handle special cases
    lower_filename = filename.lower()
    if lower_filename == 'dockerfile':
        return 'dockerfile'
    if lower_filename.startswith('.env'):
        return 'env'
    if lower_filename == 'requirements.txt':
        return 'text'
    if lower_filename == 'docker-compose.yml':
        return 'yaml'

    # Check extension
    for ext, lang in extension_map.items():
        if lower_filename.endswith(ext):
            return lang

    return 'text'


def _generate_readme(project: DBProjectAttempt, code_files: List[DBGeneratedCode]) -> str:
    """Generate a README.md file for the project ZIP."""
    readme = f"""# {project.title}

Generated by SyncBoard AI on {datetime.utcnow().strftime('%Y-%m-%d')}

## Project Status
- Status: {project.status}
- Created: {project.created_at.strftime('%Y-%m-%d')}

## Files Included
"""

    for code in code_files:
        readme += f"- `{code.filename}` ({code.language or 'unknown'})"
        if code.description:
            readme += f" - {code.description}"
        readme += "\n"

    # Add setup instructions if any file has them
    setup_instructions = next((c.setup_instructions for c in code_files if c.setup_instructions), None)
    if setup_instructions:
        readme += f"""
## Setup Instructions
{setup_instructions}
"""

    # Add dependencies if any file has them
    all_dependencies = []
    for code in code_files:
        if code.dependencies:
            all_dependencies.extend(code.dependencies)

    if all_dependencies:
        readme += f"""
## Dependencies
"""
        for dep in set(all_dependencies):
            readme += f"- {dep}\n"

    readme += """
## Getting Started

1. Extract this ZIP file
2. Install dependencies (if applicable)
3. Follow the setup instructions above
4. Run the application

## Generated by SyncBoard
This code was AI-generated as a starter template. Review and customize as needed.
"""

    return readme
