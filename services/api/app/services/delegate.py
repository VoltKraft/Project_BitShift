"""Delegate / substitute suggestion (F3).

Picks candidates in the same team who are not on leave during the requested window
and who are not the requester. Ranked by current assignment load (ascending) so the
most available person surfaces first.
"""

import uuid
from collections import Counter
from datetime import date

from sqlalchemy import and_, or_, select
from sqlalchemy.orm import Session

from app.models import LeaveRequest, Shift, ShiftAssignment, User
from app.models.enums import LeaveStatus


_BLOCKING_LEAVE_STATES = {
    LeaveStatus.submitted.value,
    LeaveStatus.delegate_review.value,
    LeaveStatus.tl_review.value,
    LeaveStatus.hr_review.value,
    LeaveStatus.approved.value,
}


def _users_on_leave(db: Session, start: date, end: date) -> set[uuid.UUID]:
    rows = db.execute(
        select(LeaveRequest.requester_id).where(
            LeaveRequest.status.in_(_BLOCKING_LEAVE_STATES),
            LeaveRequest.start_date <= end,
            LeaveRequest.end_date >= start,
        )
    ).scalars()
    return set(rows)


def _load_map(db: Session, user_ids: set[uuid.UUID], start: date, end: date) -> Counter[uuid.UUID]:
    if not user_ids:
        return Counter()
    rows = db.execute(
        select(ShiftAssignment.user_id)
        .join(Shift, Shift.id == ShiftAssignment.shift_id)
        .where(
            ShiftAssignment.user_id.in_(user_ids),
            ShiftAssignment.status == "assigned",
            Shift.service_date >= start,
            Shift.service_date <= end,
        )
    ).scalars()
    return Counter(rows)


def suggest(
    db: Session,
    *,
    requester: User,
    start: date,
    end: date,
    limit: int = 5,
) -> list[User]:
    if requester.team_id is None:
        return []

    candidates = db.execute(
        select(User).where(
            and_(
                User.team_id == requester.team_id,
                User.id != requester.id,
                User.deleted_at.is_(None),
                or_(User.role == "employee", User.role == "team_lead"),
            )
        )
    ).scalars().all()

    if not candidates:
        return []

    blocked = _users_on_leave(db, start, end)
    free = [u for u in candidates if u.id not in blocked]
    load = _load_map(db, {u.id for u in free}, start, end)
    free.sort(key=lambda u: (load.get(u.id, 0), (u.last_name or ""), (u.first_name or "")))
    return free[:limit]
