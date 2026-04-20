import uuid
from datetime import date, datetime

from fastapi import APIRouter, Depends
from pydantic import BaseModel, ConfigDict
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db import get_db
from app.models import AuditEvent
from app.permissions import require_hr_or_admin
from app.services import audit as audit_service

router = APIRouter(prefix="/api/audit", tags=["audit"])


class AuditOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    seq: int
    occurred_at: datetime
    actor_id: uuid.UUID | None
    actor_role: str | None
    action: str
    target_type: str
    target_id: uuid.UUID | None
    reason: str | None
    before_state: dict | None
    after_state: dict | None
    prev_hash: str | None
    row_hash: str


class VerificationResult(BaseModel):
    ok: bool
    checked: int
    first_bad_id: str | None


@router.get("/events", response_model=list[AuditOut])
def list_events(
    db: Session = Depends(get_db),
    _=Depends(require_hr_or_admin()),
    action: str | None = None,
    actor_id: uuid.UUID | None = None,
    since: date | None = None,
    limit: int = 200,
) -> list[AuditEvent]:
    stmt = select(AuditEvent).order_by(AuditEvent.seq.desc())
    if action is not None:
        stmt = stmt.where(AuditEvent.action == action)
    if actor_id is not None:
        stmt = stmt.where(AuditEvent.actor_id == actor_id)
    if since is not None:
        from datetime import time, timezone

        stmt = stmt.where(AuditEvent.occurred_at >= datetime.combine(since, time.min, tzinfo=timezone.utc))
    return list(db.execute(stmt.limit(max(1, min(limit, 1000)))).scalars())


@router.get("/verify", response_model=VerificationResult)
def verify_chain(db: Session = Depends(get_db), _=Depends(require_hr_or_admin())) -> VerificationResult:
    ok, checked, bad = audit_service.verify_chain(db)
    return VerificationResult(ok=ok, checked=checked, first_bad_id=bad)
