"""F14 substitution reconciliation.

Finds ShiftAssignment rows flagged ``needs_substitute`` by the API when a
sickness report lands on an already-scheduled worker, nominates up to five
substitute candidates, and nudges the team lead once per assignment.

The worker does not share ORM models with the API — it runs raw SQL against
the shared database, which keeps the two images decoupled. Idempotency is
handled with a marker in ``shift_assignments.note`` so re-entering the loop
after a crash does not double-notify.
"""

import logging

from sqlalchemy import text
from sqlalchemy.engine import Connection

from app.config import settings
from app.notify import Message, send

log = logging.getLogger("chronos.worker.substitution")

MARKER = "[worker:substitute-nudged]"
BLOCKING_LEAVE_STATUSES = (
    "SUBMITTED",
    "DELEGATE_REVIEW",
    "TL_REVIEW",
    "HR_REVIEW",
    "APPROVED",
)


def _pending_query() -> str:
    return """
    SELECT
        a.id            AS assignment_id,
        a.shift_id      AS shift_id,
        a.user_id       AS absentee_id,
        a.note          AS note,
        s.service_date  AS service_date,
        s.shift_type    AS shift_type,
        s.team_id       AS team_id,
        s.start_time    AS start_time,
        s.end_time      AS end_time
    FROM shift_assignments a
    JOIN shifts s ON s.id = a.shift_id
    WHERE a.status = 'needs_substitute'
      AND a.deleted_at IS NULL
      AND s.deleted_at IS NULL
      AND (a.note IS NULL OR position(:marker in a.note) = 0)
    ORDER BY s.service_date ASC
    LIMIT :limit
    """


def _candidate_query() -> str:
    return f"""
    SELECT u.id, u.email,
           coalesce(nullif(trim(coalesce(u.first_name, '') || ' ' || coalesce(u.last_name, '')), ''),
                    u.email) AS display_name
    FROM users u
    WHERE u.deleted_at IS NULL
      AND u.team_id = :team_id
      AND u.id <> :absentee
      AND NOT EXISTS (
          SELECT 1 FROM leave_requests l
          WHERE l.requester_id = u.id
            AND l.deleted_at IS NULL
            AND l.status IN ({", ".join(f"'{s}'" for s in BLOCKING_LEAVE_STATUSES)})
            AND l.start_date <= :service_date
            AND l.end_date   >= :service_date
      )
      AND NOT EXISTS (
          SELECT 1 FROM shift_assignments a2
          JOIN shifts s2 ON s2.id = a2.shift_id
          WHERE a2.user_id = u.id
            AND a2.status = 'assigned'
            AND s2.service_date = :service_date
            AND s2.deleted_at IS NULL
      )
    ORDER BY (
        -- Prefer people whose SHIFT_TIME preference matches this shift
        CASE WHEN EXISTS (
            SELECT 1 FROM preferences p
            WHERE p.user_id = u.id
              AND p.preference_type = 'SHIFT_TIME'
              AND p.effective_from <= :service_date
              AND (p.effective_to IS NULL OR p.effective_to >= :service_date)
              AND upper(p.payload->>'preferred') = :shift_type
        ) THEN 0 ELSE 1 END
    ), u.email
    LIMIT 5
    """


def _team_lead_query() -> str:
    return """
    SELECT u.email, u.id
    FROM users u
    WHERE u.deleted_at IS NULL
      AND u.team_id = :team_id
      AND u.role = 'team_lead'
    LIMIT 1
    """


def run(conn: Connection) -> int:
    """Poll once; return the number of assignments nudged."""
    rows = conn.execute(
        text(_pending_query()), {"marker": MARKER, "limit": settings.max_substitution_batch}
    ).mappings().all()
    processed = 0
    for row in rows:
        candidates = conn.execute(
            text(_candidate_query()),
            {
                "team_id": row["team_id"],
                "absentee": row["absentee_id"],
                "service_date": row["service_date"],
                "shift_type": row["shift_type"],
            },
        ).mappings().all()

        tl = conn.execute(text(_team_lead_query()), {"team_id": row["team_id"]}).mappings().first()
        names = ", ".join(f"{c['display_name']} <{c['email']}>" for c in candidates) or "(no eligible candidates)"
        body = (
            f"Shift {row['shift_type']} on {row['service_date']} "
            f"({row['start_time']}–{row['end_time']}) lost an assignee.\n"
            f"Suggested substitutes: {names}.\n"
            "Open /shifts in Chronos to reassign."
        )
        target = tl["email"] if tl else settings.fallback_notification_to
        if target:
            send(Message(to=target, subject="Chronos — substitute needed", body=body))
        else:
            log.info("no team lead found for team %s, skipping notification", row["team_id"])

        conn.execute(
            text(
                """
                UPDATE shift_assignments
                SET note = coalesce(note, '') || '\n' || :marker || ' ' || :summary,
                    updated_at = now()
                WHERE id = :id
                """
            ),
            {
                "id": row["assignment_id"],
                "marker": MARKER,
                "summary": f"proposed {len(candidates)} substitute(s)",
            },
        )
        processed += 1
    return processed
