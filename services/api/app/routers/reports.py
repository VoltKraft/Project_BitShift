import csv
import io
import uuid
from collections import defaultdict
from datetime import date

from fastapi import APIRouter, Depends
from fastapi.responses import Response
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db import get_db
from app.models import LeaveRequest, Shift, ShiftAssignment, User
from app.models.enums import LeaveStatus
from app.permissions import require_hr_or_admin, require_tl_or_above

router = APIRouter(prefix="/api/reports", tags=["reports"])


class LeaveSummaryRow(BaseModel):
    user_id: uuid.UUID
    user_name: str
    vacation_days: int
    sickness_days: int
    other_days: int


class ShiftSummaryRow(BaseModel):
    user_id: uuid.UUID
    user_name: str
    early_count: int
    late_count: int
    other_count: int


def _days_in(start: date, end: date, window_start: date, window_end: date) -> int:
    s = max(start, window_start)
    e = min(end, window_end)
    return max(0, (e - s).days + 1)


def _compute_leave_summary(db: Session, start: date, end: date) -> list[LeaveSummaryRow]:
    rows = db.execute(
        select(LeaveRequest).where(
            LeaveRequest.deleted_at.is_(None),
            LeaveRequest.status == LeaveStatus.approved.value,
            LeaveRequest.start_date <= end,
            LeaveRequest.end_date >= start,
        )
    ).scalars()
    per_user: dict[uuid.UUID, dict[str, int]] = defaultdict(
        lambda: {"VACATION": 0, "SICK": 0, "OTHER": 0}
    )
    for r in rows:
        per_user[r.requester_id][r.type] += _days_in(r.start_date, r.end_date, start, end)
    if not per_user:
        return []
    user_names = {
        u.id: u.display_name
        for u in db.execute(select(User).where(User.id.in_(per_user.keys()))).scalars()
    }
    return [
        LeaveSummaryRow(
            user_id=uid,
            user_name=user_names.get(uid, str(uid)),
            vacation_days=totals["VACATION"],
            sickness_days=totals["SICK"],
            other_days=totals["OTHER"],
        )
        for uid, totals in per_user.items()
    ]


def _compute_shifts_summary(
    db: Session, start: date, end: date, team_id: uuid.UUID | None
) -> list[ShiftSummaryRow]:
    stmt = (
        select(ShiftAssignment.user_id, Shift.shift_type)
        .join(Shift, Shift.id == ShiftAssignment.shift_id)
        .where(
            ShiftAssignment.status == "assigned",
            Shift.service_date >= start,
            Shift.service_date <= end,
        )
    )
    if team_id is not None:
        stmt = stmt.where(Shift.team_id == team_id)
    counts: dict[uuid.UUID, dict[str, int]] = defaultdict(
        lambda: {"EARLY": 0, "LATE": 0, "OTHER": 0}
    )
    for user_id, shift_type in db.execute(stmt):
        bucket = counts[user_id]
        bucket[shift_type if shift_type in bucket else "OTHER"] += 1
    if not counts:
        return []
    user_names = {
        u.id: u.display_name
        for u in db.execute(select(User).where(User.id.in_(counts.keys()))).scalars()
    }
    return [
        ShiftSummaryRow(
            user_id=uid,
            user_name=user_names.get(uid, str(uid)),
            early_count=c["EARLY"],
            late_count=c["LATE"],
            other_count=c["OTHER"],
        )
        for uid, c in counts.items()
    ]


@router.get("/leave", response_model=list[LeaveSummaryRow])
def leave_summary(
    start: date,
    end: date,
    db: Session = Depends(get_db),
    _=Depends(require_tl_or_above()),
) -> list[LeaveSummaryRow]:
    return _compute_leave_summary(db, start, end)


@router.get("/leave.csv")
def leave_summary_csv(
    start: date,
    end: date,
    db: Session = Depends(get_db),
    _=Depends(require_hr_or_admin()),
) -> Response:
    rows = _compute_leave_summary(db, start, end)
    buf = io.StringIO()
    writer = csv.writer(buf)
    writer.writerow(["user_id", "user_name", "vacation_days", "sickness_days", "other_days"])
    for r in rows:
        writer.writerow([r.user_id, r.user_name, r.vacation_days, r.sickness_days, r.other_days])
    return Response(
        content=buf.getvalue(),
        media_type="text/csv",
        headers={"Content-Disposition": f"attachment; filename=leave-{start}-{end}.csv"},
    )


@router.get("/sickness", response_model=list[LeaveSummaryRow])
def sickness_summary(
    start: date,
    end: date,
    db: Session = Depends(get_db),
    _=Depends(require_tl_or_above()),
) -> list[LeaveSummaryRow]:
    return [row for row in _compute_leave_summary(db, start, end) if row.sickness_days > 0]


@router.get("/shifts", response_model=list[ShiftSummaryRow])
def shifts_summary(
    start: date,
    end: date,
    db: Session = Depends(get_db),
    team_id: uuid.UUID | None = None,
    _=Depends(require_tl_or_above()),
) -> list[ShiftSummaryRow]:
    return _compute_shifts_summary(db, start, end, team_id)
