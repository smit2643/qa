from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import RedirectResponse
from sqlalchemy.orm import Session
from core.database import get_db
from core.config import settings
from modules.auth.schemas import SignupRequest, LoginRequest, TokenResponse, UserResponse
from modules.auth import service
from modules.auth import oauth as oauth_service
from modules.auth.dependencies import get_current_user
from models import User

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/signup", response_model=TokenResponse, status_code=status.HTTP_201_CREATED)
def signup(body: SignupRequest, db: Session = Depends(get_db)):
    try:
        user = service.signup(db, body.email, body.name, body.password)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    return TokenResponse(access_token=service.create_access_token(user.id))


@router.post("/login", response_model=TokenResponse)
def login(body: LoginRequest, db: Session = Depends(get_db)):
    try:
        user = service.login(db, body.email, body.password)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=str(e))
    return TokenResponse(access_token=service.create_access_token(user.id))


@router.get("/me", response_model=UserResponse)
def me(current_user: User = Depends(get_current_user)):
    return current_user


@router.get("/github/login")
def github_login():
    """Redirect user to GitHub OAuth page."""
    if not settings.github_client_id:
        raise HTTPException(status_code=501, detail="GitHub OAuth not configured")
    return RedirectResponse(oauth_service.github_login_url())


@router.get("/github/callback")
def github_callback(code: str, db: Session = Depends(get_db)):
    """GitHub redirects here with ?code=... — exchange for JWT and redirect to frontend."""
    try:
        token = oauth_service.github_callback(db, code)
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))
    return RedirectResponse(f"{settings.frontend_url}/auth/callback?token={token}")


@router.get("/google/login")
def google_login():
    """Redirect user to Google OAuth page."""
    if not settings.google_client_id:
        raise HTTPException(status_code=501, detail="Google OAuth not configured")
    return RedirectResponse(oauth_service.google_login_url())


@router.get("/google/callback")
def google_callback(code: str, db: Session = Depends(get_db)):
    try:
        token = oauth_service.google_callback(db, code)
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))
    return RedirectResponse(f"{settings.frontend_url}/auth/callback?token={token}")
