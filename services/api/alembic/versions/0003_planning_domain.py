"""planning domain: org, shifts, leave, delegates, preferences, calendar, audit

Revision ID: 0003
Revises: 0002
Create Date: 2026-04-20

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = "0003"
down_revision: Union[str, None] = "0002"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _timestamps() -> list[sa.Column]:
    return [
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("deleted_at", sa.DateTime(timezone=True)),
    ]


def upgrade() -> None:
    op.create_table(
        "departments",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("name", sa.String(length=200), nullable=False, unique=True),
        *_timestamps(),
    )
    op.create_index("ix_departments_name", "departments", ["name"], unique=True)

    op.create_table(
        "teams",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("name", sa.String(length=200), nullable=False),
        sa.Column(
            "department_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("departments.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        *_timestamps(),
        sa.UniqueConstraint("department_id", "name", name="uq_teams_department_name"),
    )
    op.create_index("ix_teams_department_id", "teams", ["department_id"])

    op.create_table(
        "projects",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("code", sa.String(length=64), nullable=False, unique=True),
        sa.Column("name", sa.String(length=200), nullable=False),
        sa.Column("description", sa.String(length=1000)),
        *_timestamps(),
    )
    op.create_index("ix_projects_code", "projects", ["code"], unique=True)

    # Extend users with org + locale columns
    op.add_column("users", sa.Column("locale", sa.String(length=10), nullable=False, server_default="en"))
    op.add_column("users", sa.Column("time_zone", sa.String(length=64), nullable=False, server_default="UTC"))
    op.add_column("users", sa.Column("department_id", postgresql.UUID(as_uuid=True)))
    op.add_column("users", sa.Column("team_id", postgresql.UUID(as_uuid=True)))
    op.create_foreign_key(
        "fk_users_department_id", "users", "departments", ["department_id"], ["id"], ondelete="SET NULL"
    )
    op.create_foreign_key(
        "fk_users_team_id", "users", "teams", ["team_id"], ["id"], ondelete="SET NULL"
    )
    op.create_index("ix_users_department_id", "users", ["department_id"])
    op.create_index("ix_users_team_id", "users", ["team_id"])

    op.create_table(
        "shifts",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("service_date", sa.Date, nullable=False),
        sa.Column("shift_type", sa.String(length=16), nullable=False),
        sa.Column("start_time", sa.Time, nullable=False),
        sa.Column("end_time", sa.Time, nullable=False),
        sa.Column("required_headcount", sa.Integer, nullable=False, server_default=sa.text("1")),
        sa.Column(
            "team_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("teams.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "project_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("projects.id", ondelete="SET NULL"),
        ),
        *_timestamps(),
        sa.UniqueConstraint("team_id", "service_date", "shift_type", name="uq_shifts_team_date_type"),
    )
    op.create_index("ix_shifts_service_date", "shifts", ["service_date"])
    op.create_index("ix_shifts_team_id", "shifts", ["team_id"])
    op.create_index("ix_shifts_project_id", "shifts", ["project_id"])

    op.create_table(
        "shift_assignments",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "shift_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("shifts.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "user_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column("status", sa.String(length=16), nullable=False, server_default="assigned"),
        sa.Column("note", sa.String(length=500)),
        *_timestamps(),
        sa.UniqueConstraint("shift_id", "user_id", name="uq_assignment_shift_user"),
    )
    op.create_index("ix_shift_assignments_shift_id", "shift_assignments", ["shift_id"])
    op.create_index("ix_shift_assignments_user_id", "shift_assignments", ["user_id"])

    op.create_table(
        "leave_requests",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "requester_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column(
            "approver_delegate_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="SET NULL"),
        ),
        sa.Column(
            "approver_tl_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="SET NULL"),
        ),
        sa.Column(
            "approver_hr_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="SET NULL"),
        ),
        sa.Column("type", sa.String(length=16), nullable=False),
        sa.Column("reason", sa.String(length=2000)),
        sa.Column("start_date", sa.Date, nullable=False),
        sa.Column("end_date", sa.Date, nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False, server_default="DRAFT"),
        sa.Column("has_certificate", sa.Boolean, nullable=False, server_default=sa.text("false")),
        sa.Column("submitted_at", sa.DateTime(timezone=True)),
        sa.Column("decided_at", sa.DateTime(timezone=True)),
        *_timestamps(),
        sa.CheckConstraint("start_date <= end_date", name="ck_leave_dates_ordered"),
    )
    op.create_index("ix_leave_requests_requester_id", "leave_requests", ["requester_id"])
    op.create_index("ix_leave_requests_start_date", "leave_requests", ["start_date"])
    op.create_index("ix_leave_requests_status", "leave_requests", ["status"])

    op.create_table(
        "delegates",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "principal_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column(
            "delegate_user_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column("valid_from", sa.Date, nullable=False),
        sa.Column("valid_to", sa.Date, nullable=False),
        *_timestamps(),
        sa.CheckConstraint("valid_from <= valid_to", name="ck_delegate_dates_ordered"),
        sa.CheckConstraint("principal_id <> delegate_user_id", name="ck_delegate_principal_differs"),
    )
    op.create_index("ix_delegates_principal_id", "delegates", ["principal_id"])
    op.create_index("ix_delegates_delegate_user_id", "delegates", ["delegate_user_id"])

    op.create_table(
        "preferences",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "user_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("preference_type", sa.String(length=32), nullable=False),
        sa.Column("payload", postgresql.JSONB, nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("effective_from", sa.Date, nullable=False),
        sa.Column("effective_to", sa.Date),
        *_timestamps(),
        sa.UniqueConstraint("user_id", "preference_type", "effective_from", name="uq_preference_user_type_from"),
    )
    op.create_index("ix_preferences_user_id", "preferences", ["user_id"])

    op.create_table(
        "calendar_events",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "user_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("event_type", sa.String(length=16), nullable=False),
        sa.Column("title", sa.String(length=200), nullable=False),
        sa.Column("starts_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("ends_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("source", sa.String(length=16), nullable=False, server_default="SYSTEM"),
        sa.Column("external_ref", sa.String(length=200)),
        sa.Column(
            "leave_request_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("leave_requests.id", ondelete="CASCADE"),
        ),
        sa.Column(
            "shift_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("shifts.id", ondelete="CASCADE"),
        ),
        *_timestamps(),
    )
    op.create_index("ix_calendar_events_user_id", "calendar_events", ["user_id"])
    op.create_index("ix_calendar_events_starts_at", "calendar_events", ["starts_at"])
    op.create_index("ix_calendar_events_event_type", "calendar_events", ["event_type"])

    op.create_table(
        "audit_events",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("seq", sa.BigInteger, autoincrement=True, nullable=False, unique=True),
        sa.Column("occurred_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column(
            "actor_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="SET NULL"),
        ),
        sa.Column("actor_role", sa.String(length=32)),
        sa.Column("action", sa.String(length=64), nullable=False),
        sa.Column("target_type", sa.String(length=64), nullable=False),
        sa.Column("target_id", postgresql.UUID(as_uuid=True)),
        sa.Column("reason", sa.String(length=2000)),
        sa.Column("before_state", postgresql.JSONB),
        sa.Column("after_state", postgresql.JSONB),
        sa.Column("prev_hash", sa.String(length=64)),
        sa.Column("row_hash", sa.String(length=64), nullable=False),
    )
    op.create_index("ix_audit_events_seq", "audit_events", ["seq"], unique=True)
    op.create_index("ix_audit_events_action", "audit_events", ["action"])


def downgrade() -> None:
    op.drop_index("ix_audit_events_action", table_name="audit_events")
    op.drop_index("ix_audit_events_seq", table_name="audit_events")
    op.drop_table("audit_events")

    op.drop_index("ix_calendar_events_event_type", table_name="calendar_events")
    op.drop_index("ix_calendar_events_starts_at", table_name="calendar_events")
    op.drop_index("ix_calendar_events_user_id", table_name="calendar_events")
    op.drop_table("calendar_events")

    op.drop_index("ix_preferences_user_id", table_name="preferences")
    op.drop_table("preferences")

    op.drop_index("ix_delegates_delegate_user_id", table_name="delegates")
    op.drop_index("ix_delegates_principal_id", table_name="delegates")
    op.drop_table("delegates")

    op.drop_index("ix_leave_requests_status", table_name="leave_requests")
    op.drop_index("ix_leave_requests_start_date", table_name="leave_requests")
    op.drop_index("ix_leave_requests_requester_id", table_name="leave_requests")
    op.drop_table("leave_requests")

    op.drop_index("ix_shift_assignments_user_id", table_name="shift_assignments")
    op.drop_index("ix_shift_assignments_shift_id", table_name="shift_assignments")
    op.drop_table("shift_assignments")

    op.drop_index("ix_shifts_project_id", table_name="shifts")
    op.drop_index("ix_shifts_team_id", table_name="shifts")
    op.drop_index("ix_shifts_service_date", table_name="shifts")
    op.drop_table("shifts")

    op.drop_index("ix_users_team_id", table_name="users")
    op.drop_index("ix_users_department_id", table_name="users")
    op.drop_constraint("fk_users_team_id", "users", type_="foreignkey")
    op.drop_constraint("fk_users_department_id", "users", type_="foreignkey")
    op.drop_column("users", "team_id")
    op.drop_column("users", "department_id")
    op.drop_column("users", "time_zone")
    op.drop_column("users", "locale")

    op.drop_index("ix_projects_code", table_name="projects")
    op.drop_table("projects")

    op.drop_index("ix_teams_department_id", table_name="teams")
    op.drop_table("teams")

    op.drop_index("ix_departments_name", table_name="departments")
    op.drop_table("departments")
