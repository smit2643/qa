# Organizations Module

Location: `backend/modules/organizations/`

Handles organization CRUD and membership management with role-based access control (RBAC).

---

## Files

| File | Responsibility |
|---|---|
| `schemas.py` | Pydantic request/response models |
| `service.py` | Business logic: CRUD, membership, role enforcement |
| `router.py` | REST endpoints under `/api/v1/organizations` |

---

## Role Hierarchy

Roles are enforced by `service.require_role()`. Hierarchy from lowest to highest:

```
viewer < member < admin < owner
```

`require_role(db, user_id, org_id, minimum_role)` raises `403` if the user's role is below the minimum.

---

## Endpoints

| Method | Path | Min Role | Description |
|---|---|---|---|
| `GET` | `/organizations` | — | List caller's organizations |
| `GET` | `/organizations/{org_id}` | viewer | Get org details |
| `PATCH` | `/organizations/{org_id}` | admin | Update org name |
| `GET` | `/organizations/{org_id}/members` | viewer | List all members |
| `POST` | `/organizations/{org_id}/members` | admin | Invite user by email |
| `DELETE` | `/organizations/{org_id}/members/{user_id}` | admin | Remove a member |
| `PATCH` | `/organizations/{org_id}/members/{user_id}/role` | admin | Change member role |

---

## Invite Flow

Inviting requires the invitee to already have an account. The endpoint looks up the user by email and adds a `Membership` record. A future enhancement will send email invites to users without accounts.

---

## Personal Org Auto-Creation

When a user signs up (email/password or OAuth), a personal organization is automatically created with:
- Name: `{user_name}'s Organization`
- Slug: `{name-kebabcase}-{uuid8}`
- User assigned as `owner`

This happens in `modules/auth/service.py` (signup) and `modules/auth/oauth.py` (_upsert_oauth_user).

---

## Tests

`backend/tests/test_organizations.py` — 10 tests covering:
- List/get orgs
- Update org name
- List members (shows owner after signup)
- Invite member, invite nonexistent user (404)
- Remove member
- Viewer role cannot update org (403)
- OAuth login endpoint graceful degradation (501 when not configured)
