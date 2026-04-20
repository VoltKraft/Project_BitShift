import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db import get_db
from app.deps import current_user
from app.models import Project, User
from app.models.enums import AuditAction
from app.permissions import require_hr_or_admin
from app.services import audit

router = APIRouter(prefix="/api/projects", tags=["projects"])


class ProjectIn(BaseModel):
    code: str = Field(min_length=1, max_length=64)
    name: str = Field(min_length=1, max_length=200)
    description: str | None = Field(default=None, max_length=1000)


class ProjectOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    code: str
    name: str
    description: str | None


@router.get("", response_model=list[ProjectOut])
def list_projects(db: Session = Depends(get_db), _: User = Depends(current_user)) -> list[Project]:
    return list(
        db.execute(
            select(Project).where(Project.deleted_at.is_(None)).order_by(Project.code)
        ).scalars()
    )


@router.post("", response_model=ProjectOut, status_code=status.HTTP_201_CREATED)
def create_project(
    payload: ProjectIn,
    db: Session = Depends(get_db),
    actor: User = Depends(require_hr_or_admin()),
) -> Project:
    if db.execute(select(Project.id).where(Project.code == payload.code)).first():
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="project code already exists")
    project = Project(code=payload.code, name=payload.name, description=payload.description)
    db.add(project)
    db.flush()
    audit.append(db, actor=actor, action=AuditAction.config_change, target_type="project", target_id=project.id, after={"code": project.code})
    db.commit()
    db.refresh(project)
    return project


@router.delete("/{project_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_project(
    project_id: uuid.UUID,
    db: Session = Depends(get_db),
    actor: User = Depends(require_hr_or_admin()),
) -> None:
    proj = db.get(Project, project_id)
    if proj is None or proj.deleted_at is not None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="not found")
    proj.deleted_at = datetime.now(timezone.utc)
    audit.append(db, actor=actor, action=AuditAction.config_change, target_type="project", target_id=proj.id, before={"code": proj.code})
    db.commit()
