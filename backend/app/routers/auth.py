from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session
from sqlalchemy import select, func

from app.core.db import get_db
from app.core.security import hash_password, verify_password, create_access_token
from app.core.errors import AppException
from app.core.rate_limit import auth_ip_limiter
from app.models.user import User
from app.schemas.auth import UserRegisterRequest, UserLoginRequest, TokenResponse
from app.schemas.user import UserResponse

router = APIRouter(prefix="/auth", tags=["Auth"])


@router.post(
    "/register",
    response_model=UserResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Register a new user account",
    dependencies=[Depends(auth_ip_limiter)],
)
def register(payload: UserRegisterRequest, db: Session = Depends(get_db)) -> User:

    """Creates a new user. Rejects duplicate emails and passwords longer than 72 bytes."""
    normalized_email = payload.email.strip().lower()
    existing_user = db.scalar(
        select(User).where(func.lower(User.email) == normalized_email)
    )
    if existing_user:
        raise AppException(
            status_code=status.HTTP_409_CONFLICT,
            code="EMAIL_EXISTS",
            message="A user with this email address already exists",
        )

    # Hash password (enforcing max 72 bytes within hash_password)
    hashed_pw = hash_password(payload.password)

    new_user = User(
        email=normalized_email,
        password_hash=hashed_pw,
        display_name=payload.display_name.strip(),
    )
    db.add(new_user)
    db.commit()
    db.refresh(new_user)
    return new_user


@router.post(
    "/login",
    response_model=TokenResponse,
    status_code=status.HTTP_200_OK,
    summary="Log in and retrieve JWT access token",
    dependencies=[Depends(auth_ip_limiter)],
)
def login(payload: UserLoginRequest, db: Session = Depends(get_db)) -> TokenResponse:

    """Authenticates user credentials and returns a Bearer access token."""
    normalized_email = payload.email.strip().lower()
    user = db.scalar(
        select(User).where(func.lower(User.email) == normalized_email)
    )

    if not user or not verify_password(payload.password, user.password_hash):
        raise AppException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            code="INVALID_CREDENTIALS",
            message="Invalid email or password",
        )

    token = create_access_token(user_id=user.id)
    return TokenResponse(access_token=token, token_type="bearer")
