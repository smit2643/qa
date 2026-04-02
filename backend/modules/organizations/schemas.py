from pydantic import BaseModel
from datetime import datetime
from models.membership import Role


class OrgResponse(BaseModel):
    id: str
    name: str
    slug: str
    plan: str
    created_at: datetime
    model_config = {"from_attributes": True}


class UpdateOrgRequest(BaseModel):
    name: str


class MemberResponse(BaseModel):
    user_id: str
    user_name: str
    user_email: str
    role: Role
    joined_at: datetime

    model_config = {"from_attributes": True}


class InviteMemberRequest(BaseModel):
    email: str
    role: Role = Role.member


class UpdateMemberRoleRequest(BaseModel):
    role: Role
