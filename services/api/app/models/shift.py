import uuid
from datetime import date, time

from sqlalchemy import Date, ForeignKey, String, Time, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db import Base
from app.models.mixins import SoftDeleteMixin, TimestampMixin, UUIDPrimaryKeyMixin


class Shift(UUIDPrimaryKeyMixin, TimestampMixin, SoftDeleteMixin, Base):
    __tablename__ = "shifts"
    __table_args__ = (
        UniqueConstraint("team_id", "service_date", "shift_type", name="uq_shifts_team_date_type"),
    )

    service_date: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    shift_type: Mapped[str] = mapped_column(String(16), nullable=False)
    start_time: Mapped[time] = mapped_column(Time, nullable=False)
    end_time: Mapped[time] = mapped_column(Time, nullable=False)
    required_headcount: Mapped[int] = mapped_column(nullable=False, default=1)

    team_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("teams.id", ondelete="CASCADE"), nullable=False, index=True
    )
    project_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("projects.id", ondelete="SET NULL"), index=True
    )

    assignments: Mapped[list["ShiftAssignment"]] = relationship(
        "ShiftAssignment", back_populates="shift", cascade="all, delete-orphan"
    )


class ShiftAssignment(UUIDPrimaryKeyMixin, TimestampMixin, SoftDeleteMixin, Base):
    __tablename__ = "shift_assignments"
    __table_args__ = (UniqueConstraint("shift_id", "user_id", name="uq_assignment_shift_user"),)

    shift_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("shifts.id", ondelete="CASCADE"), nullable=False, index=True
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    status: Mapped[str] = mapped_column(String(16), nullable=False, default="assigned")
    note: Mapped[str | None] = mapped_column(String(500))

    shift: Mapped[Shift] = relationship("Shift", back_populates="assignments")
