import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db import get_db
from app.deps import current_user
from app.models import Department, Team, User
from app.models.enums import AuditAction
from app.permissions import require_hr_or_admin
from app.services import audit

router = APIRouter(prefix="/api", tags=["organization"])


class DepartmentIn(BaseModel):
    name: str = Field(min_length=1, max_length=200)


class DepartmentOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    name: str


class TeamIn(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    department_id: uuid.UUID


class TeamOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    name: str
    department_id: uuid.UUID


@router.get("/departments", response_model=list[DepartmentOut])
def list_departments(db: Session = Depends(get_db), _: User = Depends(current_user)) -> list[Department]:
    return list(
        db.execute(
            select(Department).where(Department.deleted_at.is_(None)).order_by(Department.name)
        ).scalars()
    )


@router.post("/departments", response_model=DepartmentOut, status_code=status.HTTP_201_CREATED)
def create_department(
    payload: DepartmentIn,
    db: Session = Depends(get_db),
    actor: User = Depends(require_hr_or_admin()),
) -> Department:
    if db.execute(select(Department.id).where(Department.name == payload.name)).first():
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="department exists")
    dep = Department(name=payload.name)
    db.add(dep)
    db.flush()
    audit.append(db, actor=actor, action=AuditAction.config_change, target_type="department", target_id=dep.id, after={"name": dep.name})
    db.commit()
    db.refresh(dep)
    return dep


@router.delete("/departments/{dep_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_department(
    dep_id: uuid.UUID,
    db: Session = Depends(get_db),
    actor: User = Depends(require_hr_or_admin()),
) -> None:
    dep = db.get(Department, dep_id)
    if dep is None or dep.deleted_at is not None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="not found")
    dep.deleted_at = datetime.now(timezone.utc)
    audit.append(db, actor=actor, action=AuditAction.config_change, target_type="department", target_id=dep.id, before={"name": dep.name})
    db.commit()


@router.get("/teams", response_model=list[TeamOut])
def list_teams(
    db: Session = Depends(get_db),
    _: User = Depends(current_user),
    department_id: uuid.UUID | None = None,
) -> list[Team]:
    stmt = select(Team).where(Team.deleted_at.is_(None))
    if department_id is not None:
        stmt = stmt.where(Team.department_id == department_id)
    return list(db.execute(stmt.order_by(Team.name)).scalars())


@router.post("/teams", response_model=TeamOut, status_code=status.HTTP_201_CREATED)
def create_team(
    payload: TeamIn,
    db: Session = Depends(get_db),
    actor: User = Depends(require_hr_or_admin()),
) -> Team:
    if db.get(Department, payload.department_id) is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="department not found")
    if db.execute(
        select(Team.id).where(Team.department_id == payload.department_id, Team.name == payload.name)
    ).first():
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="team exists")
    team = Team(name=payload.name, department_id=payload.department_id)
    db.add(team)
    db.flush()
    audit.append(db, actor=actor, action=AuditAction.config_change, target_type="team", target_id=team.id, after={"name": team.name, "department_id": str(team.department_id)})
    db.commit()
    db.refresh(team)
    return team


@router.delete("/teams/{team_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_team(
    team_id: uuid.UUID,
    db: Session = Depends(get_db),
    actor: User = Depends(require_hr_or_admin()),
) -> None:
    team = db.get(Team, team_id)
    if team is None or team.deleted_at is not None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="not found")
    team.deleted_at = datetime.now(timezone.utc)
    audit.append(db, actor=actor, action=AuditAction.config_change, target_type="team", target_id=team.id, before={"name": team.name})
    db.commit()
