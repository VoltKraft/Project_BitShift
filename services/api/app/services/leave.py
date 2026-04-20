"""Leave-request workflow engine (F2/F3/F4/F13/F14).

Implements the state machine described in FS §5.1. Vacation requests follow the
full Employee → Delegate → Team Lead → HR approval chain (delegate review is
skipped when no delegate is set on the request). Sickness requests short-circuit
to APPROVED on submission and trigger F14 substitution for affected shifts.
"""

import uuid
from datetime import date, datetime, time, timezone

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import CalendarEvent, LeaveRequest, Shift, ShiftAssignment, User
from app.models.enums import (
    AuditAction,
    CalendarEventType,
    CalendarSource,
    LeaveStatus,
    LeaveType,
    Role,
)
from app.services import audit, notifications

_REVIEW_STATES = {
    LeaveStatus.delegate_review.value,
    LeaveStatus.tl_review.value,
    LeaveStatus.hr_review.value,
}

_ACTIVE_STATES = _REVIEW_STATES | {LeaveStatus.submitted.value, LeaveStatus.approved.value}


def _snapshot(r: LeaveRequest) -> dict[str, object]:
    return {
        "id": str(r.id),
        "status": r.status,
        "type": r.type,
        "requester_id": str(r.requester_id),
        "approver_delegate_id": str(r.approver_delegate_id) if r.approver_delegate_id else None,
        "approver_tl_id": str(r.approver_tl_id) if r.approver_tl_id else None,
        "approver_hr_id": str(r.approver_hr_id) if r.approver_hr_id else None,
        "start_date": r.start_date.isoformat(),
        "end_date": r.end_date.isoformat(),
        "has_certificate": r.has_certificate,
    }


def _next_review_state(req: LeaveRequest) -> str:
    """Determine the first review state for a submitted request."""
    if req.approver_delegate_id:
        return LeaveStatus.delegate_review.value
    if req.approver_tl_id:
        return LeaveStatus.tl_review.value
    return LeaveStatus.hr_review.value


def _advance_review_state(current: str, req: LeaveRequest) -> str:
    if current == LeaveStatus.delegate_review.value:
        return LeaveStatus.tl_review.value if req.approver_tl_id else LeaveStatus.hr_review.value
    if current == LeaveStatus.tl_review.value:
        return LeaveStatus.hr_review.value
    return LeaveStatus.approved.value


def _reviewer_id(req: LeaveRequest, state: str) -> uuid.UUID | None:
    return {
        LeaveStatus.delegate_review.value: req.approver_delegate_id,
        LeaveStatus.tl_review.value: req.approver_tl_id,
        LeaveStatus.hr_review.value: req.approver_hr_id,
    }.get(state)


def _has_overlap(db: Session, *, requester_id: uuid.UUID, start: date, end: date, exclude: uuid.UUID | None) -> bool:
    stmt = select(LeaveRequest.id).where(
        LeaveRequest.requester_id == requester_id,
        LeaveRequest.status.in_(_ACTIVE_STATES),
        LeaveRequest.start_date <= end,
        LeaveRequest.end_date >= start,
    )
    if exclude is not None:
        stmt = stmt.where(LeaveRequest.id != exclude)
    return db.execute(stmt).first() is not None


def _create_or_refresh_leave_events(db: Session, req: LeaveRequest) -> None:
    """Sync CalendarEvent rows for this leave request."""
    db.execute(
        CalendarEvent.__table__.delete().where(CalendarEvent.leave_request_id == req.id)
    )
    start_dt = datetime.combine(req.start_date, time.min).replace(tzinfo=timezone.utc)
    end_dt = datetime.combine(req.end_date, time.max).replace(tzinfo=timezone.utc)
    ev = CalendarEvent(
        user_id=req.requester_id,
        event_type=CalendarEventType.leave.value,
        title=f"{req.type.title()} leave",
        starts_at=start_dt,
        ends_at=end_dt,
        source=CalendarSource.system.value,
        leave_request_id=req.id,
    )
    db.add(ev)


def _flag_affected_shifts(db: Session, req: LeaveRequest) -> list[ShiftAssignment]:
    """Mark ShiftAssignments overlapping a sickness/leave as 'needs_substitute'."""
    rows = db.execute(
        select(ShiftAssignment)
        .join(Shift, Shift.id == ShiftAssignment.shift_id)
        .where(
            ShiftAssignment.user_id == req.requester_id,
            ShiftAssignment.status == "assigned",
            Shift.service_date >= req.start_date,
            Shift.service_date <= req.end_date,
        )
    ).scalars().all()
    for a in rows:
        a.status = "needs_substitute"
        a.note = (a.note or "") + f"\n[auto] flagged by leave {req.id}"
    return rows


def submit(db: Session, req: LeaveRequest, *, actor: User) -> LeaveRequest:
    if req.requester_id != actor.id and actor.role not in {Role.admin.value, Role.hr.value}:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="can only submit own requests")
    if req.status != LeaveStatus.draft.value:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=f"cannot submit in state {req.status}")
    if _has_overlap(db, requester_id=req.requester_id, start=req.start_date, end=req.end_date, exclude=req.id):
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="overlaps an existing request")

    before = _snapshot(req)
    req.submitted_at = datetime.now(timezone.utc)
    req.status = LeaveStatus.submitted.value
    if req.type == LeaveType.sick.value:
        # Sickness short-circuits to approved; F14 substitution is triggered
        req.status = LeaveStatus.approved.value
        req.decided_at = datetime.now(timezone.utc)
        _create_or_refresh_leave_events(db, req)
        affected = _flag_affected_shifts(db, req)
        audit.append(
            db,
            actor=actor,
            action=AuditAction.sickness_report,
            target_type="leave_request",
            target_id=req.id,
            before=before,
            after=_snapshot(req),
        )
        db.flush()
        # Notify team lead so they can arrange substitutes manually
        tl = db.get(User, req.approver_tl_id) if req.approver_tl_id else None
        if tl and affected:
            notifications.sickness_substitute_needed(
                tl.email, shift_ref=f"{len(affected)} shift(s) for {actor.display_name}"
            )
    else:
        req.status = _next_review_state(req)
        audit.append(
            db,
            actor=actor,
            action=AuditAction.leave_submit,
            target_type="leave_request",
            target_id=req.id,
            before=before,
            after=_snapshot(req),
        )
        reviewer = db.get(User, _reviewer_id(req, req.status)) if _reviewer_id(req, req.status) else None
        if reviewer:
            notifications.leave_submitted(
                requester_email=actor.email,
                reviewer_email=reviewer.email,
                request_id=str(req.id),
            )
    db.flush()
    return req


def approve(db: Session, req: LeaveRequest, *, actor: User, note: str | None = None) -> LeaveRequest:
    if req.status not in _REVIEW_STATES:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=f"cannot approve in state {req.status}")
    expected_reviewer = _reviewer_id(req, req.status)
    if actor.role != Role.admin.value and (expected_reviewer is None or expected_reviewer != actor.id):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="not the current reviewer")

    before = _snapshot(req)
    req.status = _advance_review_state(req.status, req)
    if req.status == LeaveStatus.approved.value:
        req.decided_at = datetime.now(timezone.utc)
        _create_or_refresh_leave_events(db, req)

    audit.append(
        db,
        actor=actor,
        action=AuditAction.leave_approve,
        target_type="leave_request",
        target_id=req.id,
        reason=note,
        before=before,
        after=_snapshot(req),
    )

    if req.status == LeaveStatus.approved.value:
        requester = db.get(User, req.requester_id)
        if requester:
            notifications.leave_decided(requester.email, str(req.id), "APPROVED")
    else:
        next_reviewer = db.get(User, _reviewer_id(req, req.status)) if _reviewer_id(req, req.status) else None
        requester = db.get(User, req.requester_id)
        if next_reviewer and requester:
            notifications.leave_submitted(
                requester_email=requester.email,
                reviewer_email=next_reviewer.email,
                request_id=str(req.id),
            )
    db.flush()
    return req


def reject(db: Session, req: LeaveRequest, *, actor: User, reason: str | None = None) -> LeaveRequest:
    if req.status not in _REVIEW_STATES:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=f"cannot reject in state {req.status}")
    expected_reviewer = _reviewer_id(req, req.status)
    if actor.role != Role.admin.value and (expected_reviewer is None or expected_reviewer != actor.id):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="not the current reviewer")

    before = _snapshot(req)
    req.status = LeaveStatus.rejected.value
    req.decided_at = datetime.now(timezone.utc)
    audit.append(
        db,
        actor=actor,
        action=AuditAction.leave_reject,
        target_type="leave_request",
        target_id=req.id,
        reason=reason,
        before=before,
        after=_snapshot(req),
    )
    requester = db.get(User, req.requester_id)
    if requester:
        notifications.leave_decided(requester.email, str(req.id), "REJECTED")
    db.flush()
    return req


def cancel(db: Session, req: LeaveRequest, *, actor: User) -> LeaveRequest:
    if req.requester_id != actor.id and actor.role not in {Role.admin.value, Role.hr.value}:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="can only cancel own requests")
    if req.status in {LeaveStatus.rejected.value, LeaveStatus.cancelled.value, LeaveStatus.overridden.value}:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=f"cannot cancel in state {req.status}")

    before = _snapshot(req)
    req.status = LeaveStatus.cancelled.value
    req.decided_at = datetime.now(timezone.utc)
    db.execute(CalendarEvent.__table__.delete().where(CalendarEvent.leave_request_id == req.id))
    audit.append(
        db,
        actor=actor,
        action=AuditAction.leave_cancel,
        target_type="leave_request",
        target_id=req.id,
        before=before,
        after=_snapshot(req),
    )
    db.flush()
    return req


def override(db: Session, req: LeaveRequest, *, actor: User, reason: str) -> LeaveRequest:
    if actor.role not in {Role.admin.value, Role.hr.value}:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="override requires HR or admin")
    before = _snapshot(req)
    req.status = LeaveStatus.overridden.value
    req.decided_at = datetime.now(timezone.utc)
    audit.append(
        db,
        actor=actor,
        action=AuditAction.leave_override,
        target_type="leave_request",
        target_id=req.id,
        reason=reason,
        before=before,
        after=_snapshot(req),
    )
    db.flush()
    return req
