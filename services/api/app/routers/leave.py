import uuid
from datetime import date, datetime

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, ConfigDict, Field, model_validator
from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from app.db import get_db
from app.deps import current_user
from app.models import LeaveRequest, User
from app.models.enums import LeaveStatus, LeaveType, Role
from app.permissions import is_hr_or_admin
from app.routers.auth import UserPublic
from app.services import delegate as delegate_service
from app.services import leave as leave_service

router = APIRouter(prefix="/api/leave-requests", tags=["leave"])


class LeaveCreate(BaseModel):
    type: LeaveType = LeaveType.vacation
    start_date: date
    end_date: date
    reason: str | None = Field(default=None, max_length=2000)
    approver_delegate_id: uuid.UUID | None = None
    approver_tl_id: uuid.UUID | None = None
    approver_hr_id: uuid.UUID | None = None
    has_certificate: bool = False

    @model_validator(mode="after")
    def _dates(self) -> "LeaveCreate":
        if self.start_date > self.end_date:
            raise ValueError("start_date must not be after end_date")
        return self


class LeaveUpdate(BaseModel):
    start_date: date | None = None
    end_date: date | None = None
    reason: str | None = Field(default=None, max_length=2000)
    approver_delegate_id: uuid.UUID | None = None
    approver_tl_id: uuid.UUID | None = None
    approver_hr_id: uuid.UUID | None = None
    has_certificate: bool | None = None


class DecisionBody(BaseModel):
    reason: str | None = Field(default=None, max_length=2000)


class OverrideBody(BaseModel):
    reason: str = Field(min_length=1, max_length=2000)


class LeaveOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    requester_id: uuid.UUID
    approver_delegate_id: uuid.UUID | None
    approver_tl_id: uuid.UUID | None
    approver_hr_id: uuid.UUID | None
    type: str
    reason: str | None
    start_date: date
    end_date: date
    status: str
    has_certificate: bool
    submitted_at: datetime | None
    decided_at: datetime | None
    created_at: datetime
    updated_at: datetime


def _get(db: Session, lid: uuid.UUID) -> LeaveRequest:
    req = db.get(LeaveRequest, lid)
    if req is None or req.deleted_at is not None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="leave request not found")
    return req


def _can_view(req: LeaveRequest, viewer: User) -> bool:
    if viewer.id == req.requester_id:
        return True
    if is_hr_or_admin(viewer):
        return True
    if viewer.id in (req.approver_delegate_id, req.approver_tl_id, req.approver_hr_id):
        return True
    if viewer.role == Role.team_lead.value and viewer.team_id:
        requester = req.requester_id
        # team lead may see requests from teammates
        owner = None  # resolved via DB if needed
        return owner is not None
    return False


@router.get("", response_model=list[LeaveOut])
def list_leave(
    db: Session = Depends(get_db),
    viewer: User = Depends(current_user),
    status_filter: str | None = None,
    requester_id: uuid.UUID | None = None,
) -> list[LeaveRequest]:
    stmt = select(LeaveRequest).where(LeaveRequest.deleted_at.is_(None))
    if not is_hr_or_admin(viewer):
        if viewer.role == Role.team_lead.value and viewer.team_id:
            team_members = select(User.id).where(User.team_id == viewer.team_id)
            stmt = stmt.where(
                or_(
                    LeaveRequest.requester_id == viewer.id,
                    LeaveRequest.approver_delegate_id == viewer.id,
                    LeaveRequest.approver_tl_id == viewer.id,
                    LeaveRequest.approver_hr_id == viewer.id,
                    LeaveRequest.requester_id.in_(team_members),
                )
            )
        else:
            stmt = stmt.where(
                or_(
                    LeaveRequest.requester_id == viewer.id,
                    LeaveRequest.approver_delegate_id == viewer.id,
                )
            )
    if status_filter is not None:
        stmt = stmt.where(LeaveRequest.status == status_filter)
    if requester_id is not None:
        stmt = stmt.where(LeaveRequest.requester_id == requester_id)
    return list(db.execute(stmt.order_by(LeaveRequest.created_at.desc())).scalars())


@router.get("/inbox", response_model=list[LeaveOut])
def inbox(db: Session = Depends(get_db), viewer: User = Depends(current_user)) -> list[LeaveRequest]:
    stmt = select(LeaveRequest).where(
        LeaveRequest.deleted_at.is_(None),
        or_(
            (
                (LeaveRequest.status == LeaveStatus.delegate_review.value)
                & (LeaveRequest.approver_delegate_id == viewer.id)
            ),
            (
                (LeaveRequest.status == LeaveStatus.tl_review.value)
                & (LeaveRequest.approver_tl_id == viewer.id)
            ),
            (
                (LeaveRequest.status == LeaveStatus.hr_review.value)
                & (LeaveRequest.approver_hr_id == viewer.id)
            ),
        ),
    )
    return list(db.execute(stmt.order_by(LeaveRequest.submitted_at.asc())).scalars())


@router.get("/delegate-suggestions", response_model=list[UserPublic])
def delegate_suggestions(
    start_date: date,
    end_date: date,
    db: Session = Depends(get_db),
    viewer: User = Depends(current_user),
) -> list[User]:
    return delegate_service.suggest(db, requester=viewer, start=start_date, end=end_date)


@router.post("", response_model=LeaveOut, status_code=status.HTTP_201_CREATED)
def create_leave(
    payload: LeaveCreate, db: Session = Depends(get_db), viewer: User = Depends(current_user)
) -> LeaveRequest:
    req = LeaveRequest(
        requester_id=viewer.id,
        type=payload.type.value,
        start_date=payload.start_date,
        end_date=payload.end_date,
        reason=payload.reason,
        approver_delegate_id=payload.approver_delegate_id,
        approver_tl_id=payload.approver_tl_id,
        approver_hr_id=payload.approver_hr_id,
        has_certificate=payload.has_certificate,
        status=LeaveStatus.draft.value,
    )
    db.add(req)
    db.commit()
    db.refresh(req)
    return req


@router.get("/{lid}", response_model=LeaveOut)
def get_leave(
    lid: uuid.UUID, db: Session = Depends(get_db), viewer: User = Depends(current_user)
) -> LeaveRequest:
    req = _get(db, lid)
    requester = db.get(User, req.requester_id)
    allowed = viewer.id == req.requester_id or is_hr_or_admin(viewer)
    allowed = allowed or viewer.id in (
        req.approver_delegate_id,
        req.approver_tl_id,
        req.approver_hr_id,
    )
    if not allowed and viewer.role == Role.team_lead.value and requester and viewer.team_id == requester.team_id:
        allowed = True
    if not allowed:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="forbidden")
    return req


@router.patch("/{lid}", response_model=LeaveOut)
def update_draft(
    lid: uuid.UUID,
    payload: LeaveUpdate,
    db: Session = Depends(get_db),
    viewer: User = Depends(current_user),
) -> LeaveRequest:
    req = _get(db, lid)
    if req.requester_id != viewer.id and not is_hr_or_admin(viewer):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="forbidden")
    if req.status != LeaveStatus.draft.value:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="only drafts are editable")
    for key, value in payload.model_dump(exclude_unset=True).items():
        setattr(req, key, value)
    db.commit()
    db.refresh(req)
    return req


@router.post("/{lid}/submit", response_model=LeaveOut)
def submit_leave(
    lid: uuid.UUID, db: Session = Depends(get_db), viewer: User = Depends(current_user)
) -> LeaveRequest:
    req = _get(db, lid)
    updated = leave_service.submit(db, req, actor=viewer)
    db.commit()
    db.refresh(updated)
    return updated


@router.post("/{lid}/approve", response_model=LeaveOut)
def approve_leave(
    lid: uuid.UUID,
    payload: DecisionBody | None = None,
    db: Session = Depends(get_db),
    viewer: User = Depends(current_user),
) -> LeaveRequest:
    req = _get(db, lid)
    updated = leave_service.approve(db, req, actor=viewer, note=(payload.reason if payload else None))
    db.commit()
    db.refresh(updated)
    return updated


@router.post("/{lid}/reject", response_model=LeaveOut)
def reject_leave(
    lid: uuid.UUID,
    payload: DecisionBody | None = None,
    db: Session = Depends(get_db),
    viewer: User = Depends(current_user),
) -> LeaveRequest:
    req = _get(db, lid)
    updated = leave_service.reject(
        db, req, actor=viewer, reason=(payload.reason if payload else None)
    )
    db.commit()
    db.refresh(updated)
    return updated


@router.post("/{lid}/cancel", response_model=LeaveOut)
def cancel_leave(
    lid: uuid.UUID, db: Session = Depends(get_db), viewer: User = Depends(current_user)
) -> LeaveRequest:
    req = _get(db, lid)
    updated = leave_service.cancel(db, req, actor=viewer)
    db.commit()
    db.refresh(updated)
    return updated


@router.post("/{lid}/override", response_model=LeaveOut)
def override_leave(
    lid: uuid.UUID,
    payload: OverrideBody,
    db: Session = Depends(get_db),
    viewer: User = Depends(current_user),
) -> LeaveRequest:
    req = _get(db, lid)
    updated = leave_service.override(db, req, actor=viewer, reason=payload.reason)
    db.commit()
    db.refresh(updated)
    return updated
