"""Email notifications. Falls back to structured-log output when SMTP is disabled.

This module intentionally keeps rendering simple (Python f-strings). Upgrading to
Jinja templates is a pure substitution later when the template set grows.
"""

import logging
import smtplib
from dataclasses import dataclass
from email.message import EmailMessage

from app.config import settings

log = logging.getLogger("chronos.notify")


@dataclass(frozen=True)
class Message:
    to: str
    subject: str
    body: str


def send(message: Message) -> None:
    if not settings.smtp_enabled:
        log.info("notification (smtp disabled) to=%s subject=%r", message.to, message.subject)
        return

    msg = EmailMessage()
    msg["From"] = settings.smtp_from
    msg["To"] = message.to
    msg["Subject"] = message.subject
    msg.set_content(message.body)

    with smtplib.SMTP(settings.smtp_host, settings.smtp_port) as client:
        if settings.smtp_use_tls:
            client.starttls()
        if settings.smtp_username:
            client.login(settings.smtp_username, settings.smtp_password or "")
        client.send_message(msg)


def leave_submitted(requester_email: str, reviewer_email: str, request_id: str) -> None:
    body = (
        f"A new leave request ({request_id}) from {requester_email} is awaiting your review.\n"
        f"Open {settings.public_url}/leave/{request_id} to respond."
    )
    send(Message(to=reviewer_email, subject="Chronos — Leave request awaits review", body=body))


def leave_decided(requester_email: str, request_id: str, status: str) -> None:
    body = (
        f"Your leave request {request_id} has been updated to status: {status}.\n"
        f"Open {settings.public_url}/leave/{request_id} for details."
    )
    send(Message(to=requester_email, subject=f"Chronos — Leave {status}", body=body))


def shift_published(user_email: str, period: str) -> None:
    body = (
        f"A new shift plan for {period} has been published.\n"
        f"Open {settings.public_url}/shifts for details."
    )
    send(Message(to=user_email, subject="Chronos — Shift plan published", body=body))


def sickness_substitute_needed(tl_email: str, shift_ref: str) -> None:
    body = (
        f"Shift {shift_ref} needs a substitute because an assignee reported sick.\n"
        f"Open {settings.public_url}/shifts to adjust the plan."
    )
    send(Message(to=tl_email, subject="Chronos — Substitute needed", body=body))
