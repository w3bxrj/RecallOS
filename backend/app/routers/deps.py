from typing import Optional
from fastapi import Depends, Request
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.orm import Session
from sqlalchemy import select

from app.core.db import get_db
from app.core.security import decode_access_token
from app.core.errors import AppException
from app.models.user import User

security_scheme = HTTPBearer(auto_error=False)


def get_current_user(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(security_scheme),
    db: Session = Depends(get_db),
) -> User:
    """FastAPI dependency to extract and authenticate the current user from Bearer JWT."""
    if credentials is None or not credentials.credentials:
        raise AppException(
            status_code=401,
            code="INVALID_TOKEN",
            message="Authorization token is missing",
        )

    user_id = decode_access_token(credentials.credentials)
    user = db.scalar(select(User).where(User.id == user_id))
    if user is None:
        raise AppException(
            status_code=401,
            code="USER_NOT_FOUND",
            message="User associated with this token does not exist",
        )
    return user
