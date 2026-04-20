import uuid

from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from pydantic import BaseModel, ConfigDict
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db import get_db
from app.deps import current_user
from app.models import User
from app.schemas import Email
from app.security import verify_password

router = APIRouter(tags=["auth"])


class LoginRequest(BaseModel):
    username: Email
    password: str


class UserPublic(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    email: Email
    first_name: str | None = None
    last_name: str | None = None
    role: str
    locale: str
    time_zone: str
    department_id: uuid.UUID | None = None
    team_id: uuid.UUID | None = None


@router.post("/auth/login", response_model=UserPublic)
def login(payload: LoginRequest, request: Request, db: Session = Depends(get_db)) -> User:
    user = db.execute(
        select(User).where(User.email == payload.username.lower(), User.deleted_at.is_(None))
    ).scalar_one_or_none()
    if user is None or not verify_password(payload.password, user.password_hash):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="invalid credentials")

    request.session["uid"] = str(user.id)
    request.session["role"] = user.role
    return user


@router.post("/auth/logout", status_code=status.HTTP_204_NO_CONTENT)
def logout(request: Request) -> Response:
    request.session.clear()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get("/auth/me", response_model=UserPublic)
def me(user: User = Depends(current_user)) -> User:
    return user
