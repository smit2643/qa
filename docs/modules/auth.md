# Auth Module

Location: `backend/modules/auth/`

Handles user registration, login, JWT token issuance, and the `get_current_user` FastAPI dependency used by all protected endpoints.

---

## Files

| File | Responsibility |
|---|---|
| `schemas.py` | Pydantic request/response models |
| `service.py` | Business logic: signup, login, token creation/decoding |
| `dependencies.py` | `get_current_user` FastAPI dependency |
| `router.py` | Endpoints: `POST /auth/signup`, `POST /auth/login`, `GET /auth/me` |

---

## Token Flow

```
Signup/Login → service.create_access_token(user_id) → JWT
JWT payload: { "sub": user_id, "exp": now + 24h }
Signed with: settings.secret_key (HS256)

Protected request:
  Authorization: Bearer <token>
  → dependencies.get_current_user()
  → decode JWT → get user_id → query DB → return User
```

---

## Signup Behavior

On signup, a personal **Organization** is automatically created for the user and they are assigned as `owner`. This is the default org used when creating projects.

Teams/multi-org invite flows are a future enhancement (org management endpoints not yet implemented).

---

## Password Storage

Passwords are hashed using `bcrypt` via `passlib`. Plain text is never stored.

OAuth2 users (GitHub/Google) have `hashed_password = None` — login via OAuth only.

---

## Security: Timing-Safe Login

The `login()` service always runs a dummy bcrypt verification even when the user is not found. This equalizes response time (~100ms) regardless of whether an email is registered, preventing email enumeration via response latency.

```python
# _DUMMY_HASH is a module-level constant
verify_password(password, _DUMMY_HASH)   # always runs on user-not-found
```

## OAuth2 (GitHub / Google)

OAuth2 login is planned for Phase 2. The `User` model has `oauth_provider` and `oauth_id` columns ready. Implementation will follow the standard OAuth2 authorization code flow:

1. Frontend redirects to `/auth/github`
2. Backend redirects to GitHub OAuth
3. GitHub redirects back with code
4. Backend exchanges code for user info
5. Upsert user record, issue JWT

---

## Dependency: `get_current_user`

Used on all protected routes:

```python
from modules.auth.dependencies import get_current_user
from models import User

@router.get("/me")
def me(current_user: User = Depends(get_current_user)):
    return current_user
```

Raises `401 Unauthorized` if token is missing, expired, or invalid.

---

## Environment Variables

| Variable | Description |
|---|---|
| `SECRET_KEY` | JWT signing key — must be 32+ random chars in production |
| `ACCESS_TOKEN_EXPIRE_MINUTES` | Token lifetime, default 1440 (24h) |
