import uuid
from datetime import datetime, timedelta, timezone
from jose import jwt, JWTError
from passlib.context import CryptContext
from sqlalchemy.orm import Session
from models import User, Organization, Membership, Role
from core.config import settings

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
ALGORITHM = "HS256"


def hash_password(password: str) -> str:
    return pwd_context.hash(password)


def verify_password(plain: str, hashed: str) -> bool:
    return pwd_context.verify(plain, hashed)


def create_access_token(user_id: str) -> str:
    expire = datetime.now(timezone.utc) + timedelta(minutes=settings.access_token_expire_minutes)
    payload = {"sub": user_id, "exp": expire, "iat": datetime.now(timezone.utc)}
    return jwt.encode(payload, settings.secret_key, algorithm=ALGORITHM)


def decode_token(token: str) -> str:
    """Decode JWT and return user_id (sub claim). Raises JWTError on invalid token."""
    payload = jwt.decode(token, settings.secret_key, algorithms=[ALGORITHM])
    user_id: str | None = payload.get("sub")
    if user_id is None:
        raise JWTError("Token missing sub claim")
    return user_id


def signup(db: Session, email: str, name: str, password: str) -> User:
    existing = db.query(User).filter(User.email == email).first()
    if existing:
        raise ValueError("Email already registered")

    user = User(
        email=email,
        name=name,
        hashed_password=hash_password(password),
    )
    db.add(user)
    db.flush()  # get user.id before committing

    # Create personal organization for new user
    slug = f"{name.lower().replace(' ', '-')}-{str(uuid.uuid4())[:8]}"
    org = Organization(name=f"{name}'s Organization", slug=slug)
    db.add(org)
    db.flush()

    membership = Membership(user_id=user.id, organization_id=org.id, role=Role.owner)
    db.add(membership)
    db.commit()
    db.refresh(user)
    return user


# Constant-time dummy hash — used to equalize timing when user is not found
_DUMMY_HASH = pwd_context.hash("dummy-password-for-timing-equalization")


def login(db: Session, email: str, password: str) -> User:
    user = db.query(User).filter(User.email == email).first()

    if not user or not user.hashed_password:
        # Run dummy verification to equalize timing and prevent email enumeration
        verify_password(password, _DUMMY_HASH)
        raise ValueError("Invalid credentials")

    if not verify_password(password, user.hashed_password):
        raise ValueError("Invalid credentials")

    if not user.is_active:
        raise ValueError("Account is deactivated")

    return user


def get_user_by_id(db: Session, user_id: str) -> User | None:
    return db.query(User).filter(User.id == user_id, User.is_active == True).first()
