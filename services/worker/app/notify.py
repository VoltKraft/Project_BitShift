"""Tiny SMTP sender used by worker jobs.

Mirrors the API's notifications module intentionally (the services are
decoupled; we don't share code). When SMTP is not configured, emails fall
back to the log so operators can see what would have been sent.
"""

import logging
import smtplib
from dataclasses import dataclass
from email.message import EmailMessage

from app.config import settings

log = logging.getLogger("chronos.worker.notify")


@dataclass(frozen=True)
class Message:
    to: str
    subject: str
    body: str


def send(message: Message) -> None:
    if not settings.smtp_enabled:
        log.info("smtp disabled → to=%s subject=%r", message.to, message.subject)
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
