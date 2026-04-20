"""Shared schema primitives."""

from __future__ import annotations

import re
from typing import Annotated

from pydantic import BeforeValidator

_EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


def _normalize_email(value: object) -> str:
    if not isinstance(value, str):
        raise TypeError("email must be a string")
    normalized = value.strip().lower()
    if not _EMAIL_RE.match(normalized):
        raise ValueError("value is not a valid email address")
    return normalized


Email = Annotated[str, BeforeValidator(_normalize_email)]
