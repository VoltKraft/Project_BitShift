"""Shift planning helpers.

- ``plan_period`` is a small rule-based auto-planner (F5/F6/F7): it creates
  Early/Late shifts for working days in a period and round-robins the team
  across them while honouring preferences and approved leaves.
- ``find_substitutes`` supports F14 by ranking team members for a given
  vacant shift slot based on current load and availability.
"""

import uuid
from dataclasses import dataclass
from datetime import date, datetime, time, timedelta, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import CalendarEvent, LeaveRequest, Preference, Shift, ShiftAssignment, Team, User
from app.models.enums import (
    AuditAction,
    CalendarEventType,
    CalendarSource,
    LeaveStatus,
    PreferenceType,
    ShiftType,
)
from app.services import audit

DEFAULT_EARLY = (time(6, 0), time(14, 0))
DEFAULT_LATE = (time(14, 0), time(22, 0))

_BLOCKING_LEAVE = {
    LeaveStatus.submitted.value,
    LeaveStatus.delegate_review.value,
    LeaveStatus.tl_review.value,
    LeaveStatus.hr_review.value,
    LeaveStatus.approved.value,
}


@dataclass
class PlanResult:
    shifts_created: int
    assignments_created: int
    unassigned: list[str]


def _is_working_day(d: date, holidays: set[date]) -> bool:
    if d.weekday() >= 5:
        return False
    return d not in holidays


def _user_on_leave(db: Session, user_id: uuid.UUID, d: date) -> bool:
    row = db.execute(
        select(LeaveRequest.id).where(
            LeaveRequest.requester_id == user_id,
            LeaveRequest.status.in_(_BLOCKING_LEAVE),
            LeaveRequest.start_date <= d,
            LeaveRequest.end_date >= d,
        )
    ).first()
    return row is not None


def _has_day_off_preference(db: Session, user_id: uuid.UUID, d: date) -> bool:
    rows = db.execute(
        select(Preference).where(
            Preference.user_id == user_id,
            Preference.preference_type == PreferenceType.day_off.value,
            Preference.effective_from <= d,
        )
    ).scalars().all()
    for p in rows:
        if p.effective_to is not None and p.effective_to < d:
            continue
        weekdays = p.payload.get("weekdays") if isinstance(p.payload, dict) else None
        if isinstance(weekdays, list) and d.weekday() in weekdays:
            return True
    return False


def _shift_time_preference(db: Session, user_id: uuid.UUID, d: date) -> str | None:
    rows = db.execute(
        select(Preference).where(
            Preference.user_id == user_id,
            Preference.preference_type == PreferenceType.shift_time.value,
            Preference.effective_from <= d,
        )
    ).scalars().all()
    for p in rows:
        if p.effective_to is not None and p.effective_to < d:
            continue
        value = p.payload.get("preferred") if isinstance(p.payload, dict) else None
        if isinstance(value, str):
            return value.upper()
    return None


def _already_assigned(db: Session, user_id: uuid.UUID, d: date) -> bool:
    row = db.execute(
        select(ShiftAssignment.id)
        .join(Shift, Shift.id == ShiftAssignment.shift_id)
        .where(
            ShiftAssignment.user_id == user_id,
            ShiftAssignment.status == "assigned",
            Shift.service_date == d,
        )
    ).first()
    return row is not None


def _create_calendar_event(user: User, shift: Shift) -> CalendarEvent:
    start_dt = datetime.combine(shift.service_date, shift.start_time).replace(tzinfo=timezone.utc)
    end_dt = datetime.combine(shift.service_date, shift.end_time).replace(tzinfo=timezone.utc)
    return CalendarEvent(
        user_id=user.id,
        event_type=CalendarEventType.shift.value,
        title=f"{shift.shift_type} shift",
        starts_at=start_dt,
        ends_at=end_dt,
        source=CalendarSource.system.value,
        shift_id=shift.id,
    )


def plan_period(
    db: Session,
    *,
    team: Team,
    period_start: date,
    period_end: date,
    required_per_shift: int = 1,
    holidays: set[date] | None = None,
    actor: User | None = None,
) -> PlanResult:
    holidays = holidays or set()
    users = db.execute(
        select(User).where(User.team_id == team.id, User.deleted_at.is_(None))
    ).scalars().all()
    if not users:
        return PlanResult(shifts_created=0, assignments_created=0, unassigned=[])

    shifts_created = 0
    assignments_created = 0
    unassigned: list[str] = []
    # Round-robin pointers per shift type
    rr_index = {ShiftType.early.value: 0, ShiftType.late.value: 0}

    day = period_start
    while day <= period_end:
        if not _is_working_day(day, holidays):
            day += timedelta(days=1)
            continue
        for shift_type, (start_t, end_t) in (
            (ShiftType.early.value, DEFAULT_EARLY),
            (ShiftType.late.value, DEFAULT_LATE),
        ):
            shift = db.execute(
                select(Shift).where(
                    Shift.team_id == team.id,
                    Shift.service_date == day,
                    Shift.shift_type == shift_type,
                    Shift.deleted_at.is_(None),
                )
            ).scalar_one_or_none()
            if shift is None:
                shift = Shift(
                    team_id=team.id,
                    service_date=day,
                    shift_type=shift_type,
                    start_time=start_t,
                    end_time=end_t,
                    required_headcount=required_per_shift,
                )
                db.add(shift)
                db.flush()
                shifts_created += 1

            current_headcount = len(
                [a for a in shift.assignments if a.status == "assigned"]
            )
            needed = max(0, shift.required_headcount - current_headcount)
            if needed == 0:
                continue

            ordered = _rank_candidates(db, users, day, shift_type, rr_index[shift_type])
            for candidate in ordered:
                if needed == 0:
                    break
                if any(a.user_id == candidate.id and a.status == "assigned" for a in shift.assignments):
                    continue
                assignment = ShiftAssignment(
                    shift_id=shift.id, user_id=candidate.id, status="assigned"
                )
                db.add(assignment)
                db.add(_create_calendar_event(candidate, shift))
                assignments_created += 1
                needed -= 1
                rr_index[shift_type] = (rr_index[shift_type] + 1) % len(users)

            if needed > 0:
                unassigned.append(f"{day.isoformat()} {shift_type} missing {needed}")

        day += timedelta(days=1)

    if actor is not None:
        audit.append(
            db,
            actor=actor,
            action=AuditAction.shift_publish,
            target_type="team",
            target_id=team.id,
            after={
                "period_start": period_start.isoformat(),
                "period_end": period_end.isoformat(),
                "shifts_created": shifts_created,
                "assignments_created": assignments_created,
                "unassigned": unassigned,
            },
        )
    db.flush()
    return PlanResult(
        shifts_created=shifts_created,
        assignments_created=assignments_created,
        unassigned=unassigned,
    )


def _rank_candidates(
    db: Session,
    users: list[User],
    day: date,
    shift_type: str,
    rr_offset: int,
) -> list[User]:
    # Rotate the list so assignments spread evenly over time
    rotated = users[rr_offset:] + users[:rr_offset]
    pool: list[tuple[int, User]] = []
    for u in rotated:
        if _user_on_leave(db, u.id, day):
            continue
        if _has_day_off_preference(db, u.id, day):
            continue
        if _already_assigned(db, u.id, day):
            continue
        pref = _shift_time_preference(db, u.id, day)
        score = 0
        if pref is not None and pref == shift_type:
            score -= 2  # prefer matching preference
        elif pref is not None:
            score += 1  # mild penalty for non-preferred
        pool.append((score, u))
    pool.sort(key=lambda pair: pair[0])
    return [u for _, u in pool]


def find_substitutes(
    db: Session, *, shift: Shift, exclude: set[uuid.UUID] | None = None, limit: int = 5
) -> list[User]:
    exclude = set(exclude or ())
    candidates = db.execute(
        select(User).where(User.team_id == shift.team_id, User.deleted_at.is_(None))
    ).scalars().all()
    ranked: list[tuple[int, User]] = []
    for u in candidates:
        if u.id in exclude:
            continue
        if _user_on_leave(db, u.id, shift.service_date):
            continue
        if _already_assigned(db, u.id, shift.service_date):
            continue
        pref = _shift_time_preference(db, u.id, shift.service_date)
        score = 0 if (pref and pref == shift.shift_type) else 1
        ranked.append((score, u))
    ranked.sort(key=lambda pair: pair[0])
    return [u for _, u in ranked[:limit]]
