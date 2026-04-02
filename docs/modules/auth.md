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

Implemented in Phase 2. Source: `backend/modules/auth/oauth.py`, routes registered in `backend/modules/auth/router.py`.

### Endpoints

| Method | Path | Description |
|---|---|---|
| `GET` | `/api/v1/auth/github/login` | Redirect user to GitHub OAuth authorization page |
| `GET` | `/api/v1/auth/github/callback` | GitHub callback — receives `?code=`, issues JWT, redirects to frontend |
| `GET` | `/api/v1/auth/google/login` | Redirect user to Google OAuth authorization page |
| `GET` | `/api/v1/auth/google/callback` | Google callback — receives `?code=`, issues JWT, redirects to frontend |

### Authorization Code Flow

```
1. Frontend navigates user to GET /api/v1/auth/github/login
          ↓
2. Backend redirects → GitHub OAuth page (github.com/login/oauth/authorize)
          ↓
3. User grants access → GitHub redirects to GET /api/v1/auth/github/callback?code=<code>
          ↓
4. Backend exchanges code for GitHub access token
          ↓
5. Backend fetches user profile + primary verified email from GitHub API
          ↓
6. Backend upserts user record (see Account Linking below)
          ↓
7. Backend issues JWT and redirects to:
   {FRONTEND_URL}/auth/callback?token=<jwt>
```

The same flow applies to Google, using Google's OAuth2 endpoints.

### Account Linking

If a user authenticates via OAuth with an email address that already exists in the database (e.g., they previously signed up with a password), the OAuth provider is linked to that existing account transparently. The user is logged in as the same account — no duplicate user is created.

If the OAuth email is new, a fresh user record and a personal organization (as owner) are created, matching the behavior of email/password signup.

### User Model OAuth Fields

| Field | Description |
|---|---|
| `oauth_provider` | `"github"` or `"google"`, or `null` for password users |
| `oauth_id` | Provider's user ID string (GitHub numeric ID, Google `sub` claim) |

OAuth users have `hashed_password = None` — they can only log in via OAuth.

### Graceful Degradation

If `GITHUB_CLIENT_ID` or `GOOGLE_CLIENT_ID` env vars are empty (not set), the corresponding login endpoint returns `501 Not Implemented`. This allows running the stack without configuring OAuth.

### GitHub-Specific Behavior

GitHub may not include the user's email in the profile response if their email is set to private. The callback handler falls back to calling `GET https://api.github.com/user/emails` and selects the first verified primary email. If no verified primary email is found, the callback returns `400 Bad Request`.

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
| `GITHUB_CLIENT_ID` | GitHub OAuth App client ID (leave empty to disable) |
| `GITHUB_CLIENT_SECRET` | GitHub OAuth App client secret |
| `GOOGLE_CLIENT_ID` | Google OAuth client ID (leave empty to disable) |
| `GOOGLE_CLIENT_SECRET` | Google OAuth client secret |
