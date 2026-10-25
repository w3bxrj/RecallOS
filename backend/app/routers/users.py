from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session

from app.core.db import get_db
from app.models.user import User
from app.routers.deps import get_current_user
from app.schemas.user import UserResponse, UserUpdateRequest

router = APIRouter(tags=["Users"])


@router.get(
    "/me",
    response_model=UserResponse,
    status_code=status.HTTP_200_OK,
    summary="Get current authenticated user profile",
)
def get_me(current_user: User = Depends(get_current_user)) -> User:
    """Returns the profile of the currently authenticated user."""
    return current_user


@router.patch(
    "/me",
    response_model=UserResponse,
    status_code=status.HTTP_200_OK,
    summary="Update current authenticated user profile",
)
def update_me(
    payload: UserUpdateRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> User:
    """Updates display name and/or exam date for the current user."""
    if payload.display_name is not None:
        current_user.display_name = payload.display_name.strip()
    if payload.exam_date is not None:
        current_user.exam_date = payload.exam_date

    db.add(current_user)
    db.commit()
    db.refresh(current_user)
    return current_user
