import logging

from fastapi import FastAPI
from starlette.middleware.sessions import SessionMiddleware

from app.config import settings
from app.routers import (
    audit,
    auth,
    calendar,
    delegates,
    exports,
    health,
    leave,
    organization,
    preferences,
    projects,
    reports,
    shifts,
    users,
    workflows,
)

logging.basicConfig(level=settings.log_level.upper())

app = FastAPI(
    title="Chronos API",
    version="0.2.0",
    description="Shift, leave, and sickness planning — FS Phase 1 implementation.",
)

app.add_middleware(
    SessionMiddleware,
    secret_key=settings.session_secret,
    session_cookie=settings.cookie_name,
    max_age=settings.session_max_age_seconds,
    same_site=settings.cookie_samesite,
    https_only=settings.cookie_secure,
)

for router in (
    health.router,
    auth.router,
    users.router,
    exports.router,
    organization.router,
    projects.router,
    leave.router,
    delegates.router,
    shifts.router,
    preferences.router,
    calendar.router,
    reports.router,
    audit.router,
    workflows.router,
):
    app.include_router(router)
