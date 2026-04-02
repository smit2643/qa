from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from core.database import get_db
from modules.auth.dependencies import get_current_user
from modules.organizations import service
from modules.organizations.schemas import (
    OrgResponse, UpdateOrgRequest,
    MemberResponse, InviteMemberRequest, UpdateMemberRoleRequest,
)
from models import User, Role

router = APIRouter(prefix="/organizations", tags=["organizations"])


@router.get("", response_model=list[OrgResponse])
def list_orgs(db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    return service.get_user_orgs(db, current_user.id)


@router.get("/{org_id}", response_model=OrgResponse)
def get_org(org_id: str, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    service.require_role(db, current_user.id, org_id, Role.viewer)
    return service.get_org(db, org_id)


@router.patch("/{org_id}", response_model=OrgResponse)
def update_org(
    org_id: str, body: UpdateOrgRequest,
    db: Session = Depends(get_db), current_user: User = Depends(get_current_user),
):
    service.require_role(db, current_user.id, org_id, Role.admin)
    return service.update_org(db, org_id, body.name)


@router.get("/{org_id}/members")
def list_members(org_id: str, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    service.require_role(db, current_user.id, org_id, Role.viewer)
    return service.list_members(db, org_id)


@router.post("/{org_id}/members")
def invite_member(
    org_id: str, body: InviteMemberRequest,
    db: Session = Depends(get_db), current_user: User = Depends(get_current_user),
):
    service.require_role(db, current_user.id, org_id, Role.admin)
    return service.invite_member(db, org_id, body.email, body.role)


@router.delete("/{org_id}/members/{user_id}", status_code=204)
def remove_member(
    org_id: str, user_id: str,
    db: Session = Depends(get_db), current_user: User = Depends(get_current_user),
):
    service.require_role(db, current_user.id, org_id, Role.admin)
    service.remove_member(db, org_id, user_id, current_user.id)


@router.patch("/{org_id}/members/{user_id}/role")
def update_member_role(
    org_id: str, user_id: str, body: UpdateMemberRoleRequest,
    db: Session = Depends(get_db), current_user: User = Depends(get_current_user),
):
    service.require_role(db, current_user.id, org_id, Role.admin)
    return service.update_member_role(db, org_id, user_id, body.role)
