"""Minimal RFC 5545 ICS generator for calendar exports."""

from datetime import datetime, timezone
from typing import Iterable


def _fmt_dt(dt: datetime) -> str:
    return dt.astimezone(timezone.utc).strftime("%Y%m%dT%H%M%SZ")


def _escape(text: str) -> str:
    return text.replace("\\", "\\\\").replace(",", "\\,").replace(";", "\\;").replace("\n", "\\n")


def build_calendar(
    events: Iterable[tuple[str, str, datetime, datetime, str | None]],
    *,
    product_id: str = "-//Chronos//EN",
    calendar_name: str = "Chronos",
) -> str:
    """events = [(uid, summary, start, end, description?)]"""
    lines = [
        "BEGIN:VCALENDAR",
        "VERSION:2.0",
        f"PRODID:{product_id}",
        f"X-WR-CALNAME:{calendar_name}",
        "CALSCALE:GREGORIAN",
    ]
    stamp = _fmt_dt(datetime.now(timezone.utc))
    for uid, summary, start, end, description in events:
        lines.extend(
            [
                "BEGIN:VEVENT",
                f"UID:{uid}",
                f"DTSTAMP:{stamp}",
                f"DTSTART:{_fmt_dt(start)}",
                f"DTEND:{_fmt_dt(end)}",
                f"SUMMARY:{_escape(summary)}",
            ]
        )
        if description:
            lines.append(f"DESCRIPTION:{_escape(description)}")
        lines.append("END:VEVENT")
    lines.append("END:VCALENDAR")
    return "\r\n".join(lines) + "\r\n"
