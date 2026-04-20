"""CLI utilities for the Chronos API.

Run inside the container, e.g.:
    docker compose -f compose.dev.yaml --env-file .env.dev exec api \\
        python -m app.cli create-admin --email you@example.com --password 'secret'
"""

import argparse
import sys
from getpass import getpass

from sqlalchemy import select

from app.db import SessionLocal
from app.models.user import User
from app.security import hash_password


def _cmd_create_admin(args: argparse.Namespace) -> int:
    email = args.email.strip().lower()
    password = args.password or getpass("Password: ")
    if not password:
        print("password is required", file=sys.stderr)
        return 2

    with SessionLocal() as db:
        existing = db.scalar(select(User).where(User.email == email))
        if existing is not None:
            print(f"user already exists: {email}", file=sys.stderr)
            return 1
        user = User(
            email=email,
            password_hash=hash_password(password),
            first_name=args.first_name,
            last_name=args.last_name,
            role="admin",
        )
        db.add(user)
        db.commit()
        print(f"created admin {email} (id={user.id})")
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="app.cli")
    sub = parser.add_subparsers(dest="command", required=True)

    admin = sub.add_parser("create-admin", help="Create an admin user")
    admin.add_argument("--email", required=True)
    admin.add_argument("--password", help="Omit to be prompted interactively")
    admin.add_argument("--first-name", dest="first_name")
    admin.add_argument("--last-name", dest="last_name")
    admin.set_defaults(func=_cmd_create_admin)

    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
