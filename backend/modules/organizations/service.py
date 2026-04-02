from sqlalchemy.orm import Session
from models import Organization, User, Membership, Role
from fastapi import HTTPException, status


def get_user_orgs(db: Session, user_id: str) -> list[Organization]:
    memberships = db.query(Membership).filter(Membership.user_id == user_id).all()
    return [m.organization for m in memberships]


def get_org(db: Session, org_id: str) -> Organization:
    org = db.query(Organization).filter(Organization.id == org_id).first()
    if not org:
        raise HTTPException(status_code=404, detail="Organization not found")
    return org


def require_role(db: Session, user_id: str, org_id: str, minimum_role: Role) -> Membership:
    """Raise 403 if user doesn't have at least minimum_role in the org."""
    role_hierarchy = [Role.viewer, Role.member, Role.admin, Role.owner]
    membership = db.query(Membership).filter(
        Membership.user_id == user_id,
        Membership.organization_id == org_id,
    ).first()
    if not membership:
        raise HTTPException(status_code=403, detail="Not a member of this organization")
    if role_hierarchy.index(membership.role) < role_hierarchy.index(minimum_role):
        raise HTTPException(status_code=403, detail=f"Requires {minimum_role.value} role or higher")
    return membership


def update_org(db: Session, org_id: str, name: str) -> Organization:
    org = get_org(db, org_id)
    org.name = name
    db.commit()
    db.refresh(org)
    return org


def list_members(db: Session, org_id: str) -> list[dict]:
    memberships = db.query(Membership).filter(Membership.organization_id == org_id).all()
    return [
        {
            "user_id": m.user_id,
            "user_name": m.user.name,
            "user_email": m.user.email,
            "role": m.role,
            "joined_at": m.created_at,
        }
        for m in memberships
    ]


def invite_member(db: Session, org_id: str, email: str, role: Role) -> Membership:
    user = db.query(User).filter(User.email == email).first()
    if not user:
        raise HTTPException(status_code=404, detail="No user found with that email")
    existing = db.query(Membership).filter(
        Membership.user_id == user.id,
        Membership.organization_id == org_id,
    ).first()
    if existing:
        raise HTTPException(status_code=400, detail="User is already a member")
    membership = Membership(user_id=user.id, organization_id=org_id, role=role)
    db.add(membership)
    db.commit()
    db.refresh(membership)
    return membership


def remove_member(db: Session, org_id: str, user_id: str, requester_id: str) -> None:
    if user_id == requester_id:
        raise HTTPException(status_code=400, detail="Cannot remove yourself")
    membership = db.query(Membership).filter(
        Membership.user_id == user_id,
        Membership.organization_id == org_id,
    ).first()
    if not membership:
        raise HTTPException(status_code=404, detail="Member not found")
    db.delete(membership)
    db.commit()


def update_member_role(db: Session, org_id: str, user_id: str, role: Role) -> Membership:
    membership = db.query(Membership).filter(
        Membership.user_id == user_id,
        Membership.organization_id == org_id,
    ).first()
    if not membership:
        raise HTTPException(status_code=404, detail="Member not found")
    membership.role = role
    db.commit()
    db.refresh(membership)
    return membership
