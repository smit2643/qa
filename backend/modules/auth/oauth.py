"""
OAuth2 authorization code flow for GitHub and Google.

Flow:
1. Frontend redirects user to /api/v1/auth/{provider}/login
2. Backend redirects to provider's OAuth page
3. Provider redirects back to /api/v1/auth/{provider}/callback?code=...
4. Backend exchanges code for user info
5. Backend upserts user record, issues JWT, redirects to frontend with token
"""
import httpx
from sqlalchemy.orm import Session
from models import User, Organization, Membership, Role
from modules.auth.service import create_access_token
from core.config import settings
import uuid


GITHUB_AUTH_URL = "https://github.com/login/oauth/authorize"
GITHUB_TOKEN_URL = "https://github.com/login/oauth/access_token"
GITHUB_USER_URL = "https://api.github.com/user"
GITHUB_EMAIL_URL = "https://api.github.com/user/emails"

GOOGLE_AUTH_URL = "https://accounts.google.com/o/oauth2/v2/auth"
GOOGLE_TOKEN_URL = "https://oauth2.googleapis.com/token"
GOOGLE_USER_URL = "https://www.googleapis.com/oauth2/v3/userinfo"


def github_login_url() -> str:
    params = (
        f"client_id={settings.github_client_id}"
        f"&scope=user:email"
        f"&redirect_uri={settings.backend_url}/api/v1/auth/github/callback"
    )
    return f"{GITHUB_AUTH_URL}?{params}"


def google_login_url() -> str:
    params = (
        f"client_id={settings.google_client_id}"
        f"&redirect_uri={settings.backend_url}/api/v1/auth/google/callback"
        f"&response_type=code"
        f"&scope=openid+email+profile"
        f"&access_type=offline"
    )
    return f"{GOOGLE_AUTH_URL}?{params}"


def _upsert_oauth_user(db: Session, email: str, name: str, provider: str, provider_id: str) -> User:
    """Find or create a user from OAuth. If email exists with different provider, link accounts."""
    user = db.query(User).filter(User.email == email).first()
    if user:
        # Link OAuth to existing account if not already linked
        if not user.oauth_provider:
            user.oauth_provider = provider
            user.oauth_id = provider_id
            db.commit()
        return user

    # New user — create with personal org
    user = User(email=email, name=name, oauth_provider=provider, oauth_id=provider_id)
    db.add(user)
    db.flush()

    slug = f"{name.lower().replace(' ', '-')}-{str(uuid.uuid4())[:8]}"
    org = Organization(name=f"{name}'s Organization", slug=slug)
    db.add(org)
    db.flush()

    membership = Membership(user_id=user.id, organization_id=org.id, role=Role.owner)
    db.add(membership)
    db.commit()
    db.refresh(user)
    return user


def github_callback(db: Session, code: str) -> str:
    """Exchange GitHub code for access token, get user info, return JWT."""
    with httpx.Client() as client:
        # Exchange code for access token
        token_res = client.post(
            GITHUB_TOKEN_URL,
            data={
                "client_id": settings.github_client_id,
                "client_secret": settings.github_client_secret,
                "code": code,
            },
            headers={"Accept": "application/json"},
        )
        token_res.raise_for_status()
        access_token = token_res.json().get("access_token")
        if not access_token:
            raise ValueError("GitHub did not return access token")

        headers = {"Authorization": f"Bearer {access_token}", "Accept": "application/json"}

        # Get user profile
        user_res = client.get(GITHUB_USER_URL, headers=headers)
        user_res.raise_for_status()
        profile = user_res.json()

        # Get primary email (may not be in profile if private)
        email = profile.get("email")
        if not email:
            email_res = client.get(GITHUB_EMAIL_URL, headers=headers)
            email_res.raise_for_status()
            emails = email_res.json()
            primary = next((e for e in emails if e.get("primary") and e.get("verified")), None)
            if not primary:
                raise ValueError("No verified primary email on GitHub account")
            email = primary["email"]

    name = profile.get("name") or profile.get("login") or email.split("@")[0]
    provider_id = str(profile["id"])

    user = _upsert_oauth_user(db, email, name, "github", provider_id)
    return create_access_token(user.id)


def google_callback(db: Session, code: str) -> str:
    """Exchange Google code for access token, get user info, return JWT."""
    with httpx.Client() as client:
        token_res = client.post(
            GOOGLE_TOKEN_URL,
            data={
                "code": code,
                "client_id": settings.google_client_id,
                "client_secret": settings.google_client_secret,
                "redirect_uri": f"{settings.backend_url}/api/v1/auth/google/callback",
                "grant_type": "authorization_code",
            },
        )
        token_res.raise_for_status()
        access_token = token_res.json().get("access_token")

        user_res = client.get(GOOGLE_USER_URL, headers={"Authorization": f"Bearer {access_token}"})
        user_res.raise_for_status()
        profile = user_res.json()

    email = profile.get("email")
    name = profile.get("name") or email.split("@")[0]
    provider_id = profile.get("sub")

    user = _upsert_oauth_user(db, email, name, "google", provider_id)
    return create_access_token(user.id)
