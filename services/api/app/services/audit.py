"""Append-only audit log with per-row SHA-256 hash chaining.

Each event's `row_hash` = sha256(prev_hash || canonical_json_payload).
Use ``append`` from within a transaction alongside the state change being audited;
an advisory lock serialises the chain so concurrent writers cannot diverge.
"""

import hashlib
import json
import uuid
from datetime import date, datetime
from typing import Any

from sqlalchemy import desc, select, text
from sqlalchemy.orm import Session

from app.models import AuditEvent, User
from app.models.enums import AuditAction

_ADVISORY_LOCK_KEY = 0x43484152  # "CHAR" in hex; arbitrary shared constant


def _json_default(value: Any) -> Any:
    if isinstance(value, (datetime, date)):
        return value.isoformat()
    if isinstance(value, uuid.UUID):
        return str(value)
    raise TypeError(f"cannot serialise {type(value).__name__}")


def _canonical(payload: dict[str, Any]) -> str:
    return json.dumps(payload, sort_keys=True, separators=(",", ":"), default=_json_default)


def _hash(prev_hash: str | None, payload: dict[str, Any]) -> str:
    h = hashlib.sha256()
    h.update((prev_hash or "").encode("utf-8"))
    h.update(_canonical(payload).encode("utf-8"))
    return h.hexdigest()


def append(
    db: Session,
    *,
    actor: User | None,
    action: AuditAction | str,
    target_type: str,
    target_id: uuid.UUID | None = None,
    reason: str | None = None,
    before: dict[str, Any] | None = None,
    after: dict[str, Any] | None = None,
) -> AuditEvent:
    db.execute(text("SELECT pg_advisory_xact_lock(:k)"), {"k": _ADVISORY_LOCK_KEY})
    prev = db.execute(select(AuditEvent).order_by(desc(AuditEvent.seq)).limit(1)).scalar_one_or_none()
    prev_hash = prev.row_hash if prev else None

    action_name = action.value if isinstance(action, AuditAction) else action
    payload: dict[str, Any] = {
        "actor_id": str(actor.id) if actor else None,
        "actor_role": actor.role if actor else None,
        "action": action_name,
        "target_type": target_type,
        "target_id": str(target_id) if target_id else None,
        "reason": reason,
        "before": before,
        "after": after,
    }

    event = AuditEvent(
        actor_id=actor.id if actor else None,
        actor_role=actor.role if actor else None,
        action=action_name,
        target_type=target_type,
        target_id=target_id,
        reason=reason,
        before_state=before,
        after_state=after,
        prev_hash=prev_hash,
        row_hash=_hash(prev_hash, payload),
    )
    db.add(event)
    db.flush()
    return event


def verify_chain(db: Session) -> tuple[bool, int, str | None]:
    """Recompute the chain from the beginning. Returns (ok, checked, first_bad_id)."""
    prev_hash: str | None = None
    checked = 0
    for ev in db.execute(select(AuditEvent).order_by(AuditEvent.seq)).scalars():
        payload = {
            "actor_id": str(ev.actor_id) if ev.actor_id else None,
            "actor_role": ev.actor_role,
            "action": ev.action,
            "target_type": ev.target_type,
            "target_id": str(ev.target_id) if ev.target_id else None,
            "reason": ev.reason,
            "before": ev.before_state,
            "after": ev.after_state,
        }
        expected = _hash(prev_hash, payload)
        if ev.prev_hash != prev_hash or ev.row_hash != expected:
            return False, checked, str(ev.id)
        prev_hash = ev.row_hash
        checked += 1
    return True, checked, None
