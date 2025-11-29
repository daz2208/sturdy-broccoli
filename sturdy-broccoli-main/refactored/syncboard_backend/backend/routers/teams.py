"""
Teams Router for SyncBoard 3.0 Collaboration Features.

Endpoints:
- POST /teams - Create a new team
- GET /teams - List user's teams
- GET /teams/{team_id} - Get team details
- PUT /teams/{team_id} - Update team settings
- DELETE /teams/{team_id} - Delete team

- POST /teams/{team_id}/members - Add team member
- GET /teams/{team_id}/members - List team members
- PUT /teams/{team_id}/members/{username} - Update member role
- DELETE /teams/{team_id}/members/{username} - Remove member

- POST /teams/{team_id}/invitations - Create invitation
- GET /teams/{team_id}/invitations - List invitations
- POST /teams/invitations/{token}/accept - Accept invitation
- POST /teams/invitations/{token}/decline - Decline invitation

- POST /teams/{team_id}/knowledge-bases - Share KB with team
- GET /teams/{team_id}/knowledge-bases - List shared KBs
- DELETE /teams/{team_id}/knowledge-bases/{kb_id} - Unshare KB

- GET /teams/{team_id}/activity - Get team activity log
"""

import uuid
import secrets
import logging
from datetime import datetime, timedelta
from typing import Optional, List
from fastapi import APIRouter, HTTPException, Depends, Request, Query
from sqlalchemy.orm import Session
from pydantic import BaseModel, Field, EmailStr, ConfigDict
from slugify import slugify
from slowapi import Limiter
from slowapi.util import get_remote_address

from ..models import User
from ..dependencies import get_current_user
from ..database import get_db
from ..db_models import (
    DBTeam, DBTeamMember, DBTeamInvitation, DBTeamKnowledgeBase,
    DBKnowledgeBase, DBActivityLog
)

logger = logging.getLogger(__name__)
limiter = Limiter(key_func=get_remote_address)

router = APIRouter(
    prefix="/teams",
    tags=["teams"],
    responses={401: {"description": "Unauthorized"}},
)


# =============================================================================
# Request/Response Models
# =============================================================================

class TeamCreate(BaseModel):
    name: str = Field(..., min_length=2, max_length=255)
    description: Optional[str] = None
    is_public: bool = False


class TeamUpdate(BaseModel):
    name: Optional[str] = Field(None, min_length=2, max_length=255)
    description: Optional[str] = None
    is_public: Optional[bool] = None
    allow_member_invites: Optional[bool] = None


class TeamResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    name: str
    slug: str
    description: Optional[str]
    owner_username: str
    is_public: bool
    member_count: int
    kb_count: int
    created_at: datetime
    user_role: Optional[str] = None


class MemberAdd(BaseModel):
    username: str
    role: str = Field("member", pattern="^(admin|member|viewer)$")


class MemberUpdate(BaseModel):
    role: str = Field(..., pattern="^(admin|member|viewer)$")
    can_invite: Optional[bool] = None
    can_edit_docs: Optional[bool] = None
    can_delete_docs: Optional[bool] = None


class MemberResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    username: str
    role: str
    can_invite: bool
    can_edit_docs: bool
    can_delete_docs: bool
    can_manage_kb: bool
    joined_at: datetime
    last_active_at: Optional[datetime] = None


class InvitationCreate(BaseModel):
    email: EmailStr
    role: str = Field("member", pattern="^(admin|member|viewer)$")
    message: Optional[str] = None


class InvitationResponse(BaseModel):
    id: str
    email: str
    role: str
    status: str
    invited_by: Optional[str]
    expires_at: datetime
    created_at: datetime

    class Config:
        from_attributes = True


class ShareKBRequest(BaseModel):
    knowledge_base_id: str
    access_level: str = Field("read", pattern="^(read|write|admin)$")


class ActivityResponse(BaseModel):
    id: int
    action: str
    resource_type: str
    resource_id: Optional[str]
    resource_name: Optional[str]
    username: Optional[str]
    created_at: datetime

    class Config:
        from_attributes = True


# =============================================================================
# Helper Functions
# =============================================================================

def get_user_role_in_team(db: Session, team_id: str, username: str) -> Optional[str]:
    """Get user's role in a team, or None if not a member."""
    member = db.query(DBTeamMember).filter(
        DBTeamMember.team_id == team_id,
        DBTeamMember.username == username
    ).first()
    return member.role if member else None


def require_team_role(db: Session, team_id: str, username: str, min_role: str = "member"):
    """Require user to have at least the specified role in the team."""
    role_hierarchy = {"owner": 4, "admin": 3, "member": 2, "viewer": 1}

    role = get_user_role_in_team(db, team_id, username)
    if not role:
        raise HTTPException(status_code=403, detail="Not a team member")

    if role_hierarchy.get(role, 0) < role_hierarchy.get(min_role, 0):
        raise HTTPException(status_code=403, detail=f"Requires {min_role} role or higher")

    return role


def log_activity(
    db: Session,
    action: str,
    resource_type: str,
    resource_id: str = None,
    resource_name: str = None,
    username: str = None,
    team_id: str = None,
    kb_id: str = None,
    details: str = None
):
    """Log an activity event."""
    activity = DBActivityLog(
        team_id=team_id,
        knowledge_base_id=kb_id,
        username=username,
        action=action,
        resource_type=resource_type,
        resource_id=resource_id,
        resource_name=resource_name,
        details=details
    )
    db.add(activity)


# =============================================================================
# Team CRUD Endpoints
# =============================================================================

@router.post("", response_model=TeamResponse)
async def create_team(
    req: TeamCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Create a new team."""
    # Generate slug from name
    base_slug = slugify(req.name, max_length=90)
    slug = base_slug
    counter = 1

    # Ensure unique slug
    while db.query(DBTeam).filter(DBTeam.slug == slug).first():
        slug = f"{base_slug}-{counter}"
        counter += 1

    team = DBTeam(
        id=str(uuid.uuid4()),
        name=req.name,
        slug=slug,
        description=req.description,
        owner_username=current_user.username,
        is_public=req.is_public
    )
    db.add(team)

    # Add owner as team member
    member = DBTeamMember(
        team_id=team.id,
        username=current_user.username,
        role="owner",
        can_invite=True,
        can_edit_docs=True,
        can_delete_docs=True,
        can_manage_kb=True
    )
    db.add(member)

    log_activity(db, "created", "team", team.id, team.name, current_user.username, team.id)
    db.commit()

    logger.info(f"Team created: {team.name} by {current_user.username}")

    return TeamResponse(
        **{c.name: getattr(team, c.name) for c in team.__table__.columns},
        user_role="owner"
    )


@router.get("", response_model=List[TeamResponse])
async def list_teams(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """List all teams the user is a member of."""
    memberships = db.query(DBTeamMember).filter(
        DBTeamMember.username == current_user.username
    ).all()

    teams = []
    for membership in memberships:
        team = db.query(DBTeam).filter(DBTeam.id == membership.team_id).first()
        if team:
            teams.append(TeamResponse(
                **{c.name: getattr(team, c.name) for c in team.__table__.columns},
                user_role=membership.role
            ))

    return teams


@router.get("/{team_id}", response_model=TeamResponse)
async def get_team(
    team_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Get team details."""
    team = db.query(DBTeam).filter(DBTeam.id == team_id).first()
    if not team:
        raise HTTPException(status_code=404, detail="Team not found")

    role = get_user_role_in_team(db, team_id, current_user.username)
    if not role and not team.is_public:
        raise HTTPException(status_code=403, detail="Not a team member")

    return TeamResponse(
        **{c.name: getattr(team, c.name) for c in team.__table__.columns},
        user_role=role
    )


@router.put("/{team_id}", response_model=TeamResponse)
async def update_team(
    team_id: str,
    req: TeamUpdate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Update team settings. Requires admin role."""
    require_team_role(db, team_id, current_user.username, "admin")

    team = db.query(DBTeam).filter(DBTeam.id == team_id).first()
    if not team:
        raise HTTPException(status_code=404, detail="Team not found")

    if req.name is not None:
        team.name = req.name
    if req.description is not None:
        team.description = req.description
    if req.is_public is not None:
        team.is_public = req.is_public
    if req.allow_member_invites is not None:
        team.allow_member_invites = req.allow_member_invites

    log_activity(db, "updated", "team", team.id, team.name, current_user.username, team.id)
    db.commit()

    role = get_user_role_in_team(db, team_id, current_user.username)
    return TeamResponse(
        **{c.name: getattr(team, c.name) for c in team.__table__.columns},
        user_role=role
    )


@router.delete("/{team_id}")
async def delete_team(
    team_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Delete a team. Requires owner role."""
    team = db.query(DBTeam).filter(DBTeam.id == team_id).first()
    if not team:
        raise HTTPException(status_code=404, detail="Team not found")

    if team.owner_username != current_user.username:
        raise HTTPException(status_code=403, detail="Only team owner can delete")

    db.delete(team)
    db.commit()

    logger.info(f"Team deleted: {team_id} by {current_user.username}")
    return {"message": "Team deleted"}


# =============================================================================
# Member Management Endpoints
# =============================================================================

@router.get("/{team_id}/members", response_model=List[MemberResponse])
async def list_members(
    team_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """List all team members."""
    require_team_role(db, team_id, current_user.username, "viewer")

    members = db.query(DBTeamMember).filter(DBTeamMember.team_id == team_id).all()
    return [MemberResponse(**{c.name: getattr(m, c.name) for c in m.__table__.columns if c.name != 'id' and c.name != 'team_id'}) for m in members]


@router.put("/{team_id}/members/{username}", response_model=MemberResponse)
async def update_member(
    team_id: str,
    username: str,
    req: MemberUpdate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Update a member's role/permissions. Requires admin role."""
    require_team_role(db, team_id, current_user.username, "admin")

    member = db.query(DBTeamMember).filter(
        DBTeamMember.team_id == team_id,
        DBTeamMember.username == username
    ).first()

    if not member:
        raise HTTPException(status_code=404, detail="Member not found")

    if member.role == "owner":
        raise HTTPException(status_code=403, detail="Cannot modify owner role")

    member.role = req.role
    if req.can_invite is not None:
        member.can_invite = req.can_invite
    if req.can_edit_docs is not None:
        member.can_edit_docs = req.can_edit_docs
    if req.can_delete_docs is not None:
        member.can_delete_docs = req.can_delete_docs

    db.commit()

    return MemberResponse(**{c.name: getattr(member, c.name) for c in member.__table__.columns if c.name != 'id' and c.name != 'team_id'})


@router.delete("/{team_id}/members/{username}")
async def remove_member(
    team_id: str,
    username: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Remove a member from the team. Requires admin role (or self-removal)."""
    if username != current_user.username:
        require_team_role(db, team_id, current_user.username, "admin")

    member = db.query(DBTeamMember).filter(
        DBTeamMember.team_id == team_id,
        DBTeamMember.username == username
    ).first()

    if not member:
        raise HTTPException(status_code=404, detail="Member not found")

    if member.role == "owner":
        raise HTTPException(status_code=403, detail="Cannot remove team owner")

    # Update team member count
    team = db.query(DBTeam).filter(DBTeam.id == team_id).first()
    if team:
        team.member_count -= 1

    db.delete(member)
    log_activity(db, "removed", "team_member", username, username, current_user.username, team_id)
    db.commit()

    return {"message": "Member removed"}


# =============================================================================
# Invitation Endpoints
# =============================================================================

@router.post("/{team_id}/invitations", response_model=InvitationResponse)
@limiter.limit("10/minute")
async def create_invitation(
    team_id: str,
    req: InvitationCreate,
    request: Request,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Create a team invitation."""
    role = require_team_role(db, team_id, current_user.username, "member")

    # Check if user has invite permission
    member = db.query(DBTeamMember).filter(
        DBTeamMember.team_id == team_id,
        DBTeamMember.username == current_user.username
    ).first()

    if not member.can_invite and role not in ["owner", "admin"]:
        raise HTTPException(status_code=403, detail="No permission to invite")

    # Check for existing pending invitation
    existing = db.query(DBTeamInvitation).filter(
        DBTeamInvitation.team_id == team_id,
        DBTeamInvitation.email == req.email,
        DBTeamInvitation.status == "pending"
    ).first()

    if existing:
        raise HTTPException(status_code=400, detail="Invitation already pending")

    invitation = DBTeamInvitation(
        id=str(uuid.uuid4()),
        team_id=team_id,
        email=req.email,
        role=req.role,
        token=secrets.token_urlsafe(48),
        message=req.message,
        invited_by=current_user.username,
        expires_at=datetime.utcnow() + timedelta(days=7)
    )
    db.add(invitation)

    log_activity(db, "invited", "team_member", req.email, req.email, current_user.username, team_id)
    db.commit()

    return InvitationResponse(**{c.name: getattr(invitation, c.name) for c in invitation.__table__.columns if c.name not in ['token', 'invited_username']})


@router.get("/{team_id}/invitations", response_model=List[InvitationResponse])
async def list_invitations(
    team_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """List pending team invitations."""
    require_team_role(db, team_id, current_user.username, "admin")

    invitations = db.query(DBTeamInvitation).filter(
        DBTeamInvitation.team_id == team_id,
        DBTeamInvitation.status == "pending"
    ).all()

    return [InvitationResponse(**{c.name: getattr(inv, c.name) for c in inv.__table__.columns if c.name not in ['token', 'invited_username']}) for inv in invitations]


@router.post("/invitations/{token}/accept")
async def accept_invitation(
    token: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Accept a team invitation."""
    invitation = db.query(DBTeamInvitation).filter(
        DBTeamInvitation.token == token,
        DBTeamInvitation.status == "pending"
    ).first()

    if not invitation:
        raise HTTPException(status_code=404, detail="Invitation not found or expired")

    if invitation.expires_at < datetime.utcnow():
        invitation.status = "expired"
        db.commit()
        raise HTTPException(status_code=400, detail="Invitation has expired")

    # Check if already a member
    existing = db.query(DBTeamMember).filter(
        DBTeamMember.team_id == invitation.team_id,
        DBTeamMember.username == current_user.username
    ).first()

    if existing:
        raise HTTPException(status_code=400, detail="Already a team member")

    # Add as member
    member = DBTeamMember(
        team_id=invitation.team_id,
        username=current_user.username,
        role=invitation.role
    )
    db.add(member)

    # Update invitation
    invitation.status = "accepted"
    invitation.responded_at = datetime.utcnow()

    # Update team member count
    team = db.query(DBTeam).filter(DBTeam.id == invitation.team_id).first()
    if team:
        team.member_count += 1

    log_activity(db, "joined", "team", invitation.team_id, team.name if team else None, current_user.username, invitation.team_id)
    db.commit()

    return {"message": "Joined team successfully", "team_id": invitation.team_id}


@router.delete("/{team_id}/invitations/{invitation_id}")
async def cancel_team_invitation(
    team_id: str,
    invitation_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Cancel a pending team invitation.

    Args:
        team_id: Team ID
        invitation_id: Invitation ID to cancel
        current_user: Must be team admin

    Returns:
        Success message
    """
    require_team_role(db, team_id, current_user.username, "admin")

    invitation = db.query(DBTeamInvitation).filter(
        DBTeamInvitation.id == invitation_id,
        DBTeamInvitation.team_id == team_id,
        DBTeamInvitation.status == "pending"
    ).first()

    if not invitation:
        raise HTTPException(status_code=404, detail="Invitation not found or already processed")

    invitation.status = "cancelled"
    invitation.responded_at = datetime.utcnow()
    db.commit()

    return {"message": "Invitation cancelled successfully"}


# =============================================================================
# Knowledge Base Sharing Endpoints
# =============================================================================

@router.post("/{team_id}/knowledge-bases")
async def share_kb_with_team(
    team_id: str,
    req: ShareKBRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Share a knowledge base with the team."""
    require_team_role(db, team_id, current_user.username, "admin")

    # Verify KB exists and user owns it
    kb = db.query(DBKnowledgeBase).filter(
        DBKnowledgeBase.id == req.knowledge_base_id,
        DBKnowledgeBase.owner_username == current_user.username
    ).first()

    if not kb:
        raise HTTPException(status_code=404, detail="Knowledge base not found or not owned")

    # Check if already shared
    existing = db.query(DBTeamKnowledgeBase).filter(
        DBTeamKnowledgeBase.team_id == team_id,
        DBTeamKnowledgeBase.knowledge_base_id == req.knowledge_base_id
    ).first()

    if existing:
        existing.access_level = req.access_level
    else:
        share = DBTeamKnowledgeBase(
            team_id=team_id,
            knowledge_base_id=req.knowledge_base_id,
            access_level=req.access_level,
            shared_by=current_user.username
        )
        db.add(share)

        # Update team KB count
        team = db.query(DBTeam).filter(DBTeam.id == team_id).first()
        if team:
            team.kb_count += 1

    log_activity(db, "shared", "knowledge_base", kb.id, kb.name, current_user.username, team_id, kb.id)
    db.commit()

    return {"message": "Knowledge base shared", "access_level": req.access_level}


@router.get("/{team_id}/knowledge-bases")
async def list_shared_kbs(
    team_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """List knowledge bases shared with the team."""
    require_team_role(db, team_id, current_user.username, "viewer")

    shares = db.query(DBTeamKnowledgeBase).filter(DBTeamKnowledgeBase.team_id == team_id).all()

    result = []
    for share in shares:
        kb = db.query(DBKnowledgeBase).filter(DBKnowledgeBase.id == share.knowledge_base_id).first()
        if kb:
            result.append({
                "id": kb.id,
                "name": kb.name,
                "description": kb.description,
                "document_count": kb.document_count,
                "access_level": share.access_level,
                "shared_by": share.shared_by,
                "shared_at": share.shared_at
            })

    return result


@router.delete("/{team_id}/knowledge-bases/{kb_id}")
async def unlink_kb_from_team(
    team_id: str,
    kb_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Remove a knowledge base from the team.

    Args:
        team_id: Team ID
        kb_id: Knowledge base ID to remove
        current_user: Must be team admin

    Returns:
        Success message
    """
    require_team_role(db, team_id, current_user.username, "admin")

    share = db.query(DBTeamKnowledgeBase).filter(
        DBTeamKnowledgeBase.team_id == team_id,
        DBTeamKnowledgeBase.knowledge_base_id == kb_id
    ).first()

    if not share:
        raise HTTPException(status_code=404, detail="Knowledge base not shared with this team")

    # Get KB name for activity log
    kb = db.query(DBKnowledgeBase).filter(DBKnowledgeBase.id == kb_id).first()
    kb_name = kb.name if kb else kb_id

    db.delete(share)

    # Update team KB count
    team = db.query(DBTeam).filter(DBTeam.id == team_id).first()
    if team and team.kb_count > 0:
        team.kb_count -= 1

    log_activity(db, "unshared", "knowledge_base", kb_id, kb_name, current_user.username, team_id, kb_id)
    db.commit()

    return {"message": "Knowledge base removed from team"}


# =============================================================================
# Activity Log Endpoint
# =============================================================================

@router.get("/{team_id}/activity", response_model=List[ActivityResponse])
async def get_team_activity(
    team_id: str,
    limit: int = Query(50, ge=1, le=200),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Get recent team activity."""
    require_team_role(db, team_id, current_user.username, "viewer")

    activities = db.query(DBActivityLog).filter(
        DBActivityLog.team_id == team_id
    ).order_by(DBActivityLog.created_at.desc()).limit(limit).all()

    return [ActivityResponse(**{c.name: getattr(a, c.name) for c in a.__table__.columns if c.name not in ['team_id', 'knowledge_base_id', 'details']}) for a in activities]
