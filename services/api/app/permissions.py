"""Role-based access control primitives.

Chronos recognises four roles: employee, team_lead, hr, admin.
Higher privileges implicitly grant the lower ones where it makes sense
(admin does everything, hr can read everyone's data but only HR actions).
"""

from collections.abc import Callable
from functools import wraps
from typing import Iterable

from fastapi import Depends, HTTPException, status

from app.deps import current_user
from app.models import User
from app.models.enums import Role

_ADMIN_ROLES: set[str] = {Role.admin.value}
_HR_OR_ADMIN: set[str] = {Role.admin.value, Role.hr.value}
_TL_OR_ABOVE: set[str] = {Role.admin.value, Role.hr.value, Role.team_lead.value}


def require_roles(*allowed: Role | str) -> Callable[[User], User]:
    names = {r.value if isinstance(r, Role) else r for r in allowed}

    def _dep(user: User = Depends(current_user)) -> User:
        if user.role not in names:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"requires one of: {sorted(names)}",
            )
        return user

    _dep.__name__ = f"require_roles_{'_'.join(sorted(names))}"
    return _dep


def require_admin() -> Callable[[User], User]:
    return require_roles(Role.admin)


def require_hr_or_admin() -> Callable[[User], User]:
    return require_roles(Role.hr, Role.admin)


def require_tl_or_above() -> Callable[[User], User]:
    return require_roles(Role.team_lead, Role.hr, Role.admin)


def is_hr_or_admin(user: User) -> bool:
    return user.role in _HR_OR_ADMIN


def is_admin(user: User) -> bool:
    return user.role in _ADMIN_ROLES


def is_tl_or_above(user: User) -> bool:
    return user.role in _TL_OR_ABOVE


def can_view_user(viewer: User, target: User) -> bool:
    if viewer.id == target.id:
        return True
    if is_hr_or_admin(viewer):
        return True
    if viewer.role == Role.team_lead.value and viewer.team_id and viewer.team_id == target.team_id:
        return True
    return False


def assert_can_view_user(viewer: User, target: User) -> None:
    if not can_view_user(viewer, target):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="forbidden")


def assert_any(predicate: bool, message: str = "forbidden") -> None:
    if not predicate:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=message)
