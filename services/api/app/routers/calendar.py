import uuid
from datetime import date

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import Response
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db import get_db
from app.deps import current_user
from app.models import CalendarEvent, User
from app.permissions import can_view_user
from app.services.ics import build_calendar

router = APIRouter(prefix="/api/calendar", tags=["calendar"])


@router.get("/{user_id}.ics")
def export_ics(
    user_id: uuid.UUID,
    db: Session = Depends(get_db),
    viewer: User = Depends(current_user),
    start: date | None = None,
    end: date | None = None,
) -> Response:
    target = db.get(User, user_id)
    if target is None or target.deleted_at is not None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="user not found")
    if not can_view_user(viewer, target):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="forbidden")
    stmt = select(CalendarEvent).where(
        CalendarEvent.user_id == user_id, CalendarEvent.deleted_at.is_(None)
    )
    if start is not None:
        from datetime import datetime, time, timezone

        stmt = stmt.where(CalendarEvent.ends_at >= datetime.combine(start, time.min, tzinfo=timezone.utc))
    if end is not None:
        from datetime import datetime, time, timezone

        stmt = stmt.where(CalendarEvent.starts_at <= datetime.combine(end, time.max, tzinfo=timezone.utc))
    events = db.execute(stmt.order_by(CalendarEvent.starts_at)).scalars().all()
    body = build_calendar(
        (f"{ev.id}@chronos", ev.title, ev.starts_at, ev.ends_at, ev.event_type) for ev in events
    )
    return Response(
        content=body,
        media_type="text/calendar",
        headers={"Content-Disposition": f"attachment; filename=chronos-{user_id}.ics"},
    )
