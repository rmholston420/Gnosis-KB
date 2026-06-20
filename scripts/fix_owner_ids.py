#!/usr/bin/env python3
"""
fix_owner_ids.py — One-off CLI migration script.

Reassigns notes with legacy owner_id=0 (the pre-multi-user sentinel) to a
specified target user.  After running this script, no note in the database
should have owner_id=0 and normal users will be able to access their migrated
notes.

Usage
-----
    # Dry-run: shows what would change without writing to DB
    python scripts/fix_owner_ids.py --target-user 1 --dry-run

    # Apply the fix
    python scripts/fix_owner_ids.py --target-user 1

    # Reassign to user 2 and restrict to a specific folder
    python scripts/fix_owner_ids.py --target-user 2 --folder 00-inbox

Environment
-----------
Requires DATABASE_URL (or ASYNC_DATABASE_URL) in the environment or a .env
file in the repo root.  Example:
    DATABASE_URL=postgresql+asyncpg://gnosis:gnosis@localhost:5432/gnosis_db
"""

import argparse
import asyncio
import os
import sys
from pathlib import Path

# Allow running from repo root without installing the package
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "backend"))

from dotenv import load_dotenv  # noqa: E402
load_dotenv(Path(__file__).resolve().parents[1] / ".env")

from sqlalchemy import select, update  # noqa: E402
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker  # noqa: E402


async def run(target_user_id: int, folder: str | None, dry_run: bool) -> None:
    db_url = os.getenv("ASYNC_DATABASE_URL") or os.getenv("DATABASE_URL")
    if not db_url:
        print("ERROR: Set DATABASE_URL or ASYNC_DATABASE_URL in environment or .env file.", file=sys.stderr)
        sys.exit(1)

    # Ensure async-compatible driver is used
    if db_url.startswith("postgresql://"):
        db_url = db_url.replace("postgresql://", "postgresql+asyncpg://", 1)
    elif db_url.startswith("sqlite:///"):
        db_url = db_url.replace("sqlite:///", "sqlite+aiosqlite:///", 1)

    engine = create_async_engine(db_url, echo=False)
    Session = async_sessionmaker(engine, expire_on_commit=False)

    async with Session() as session:
        # Lazy import to avoid circular deps at module level
        from gnosis.models.note import Note  # noqa: PLC0415
        from gnosis.models.user import User  # noqa: PLC0415

        # Verify target user exists
        user_result = await session.execute(select(User).where(User.id == target_user_id))
        target_user = user_result.scalar_one_or_none()
        if not target_user:
            print(f"ERROR: No user with id={target_user_id} found in the database.", file=sys.stderr)
            sys.exit(1)

        # Collect affected notes
        stmt = select(Note).where(Note.owner_id == 0, Note.is_deleted.is_(False))
        if folder:
            stmt = stmt.where(Note.folder == folder)

        result = await session.execute(stmt)
        notes = result.scalars().all()

        if not notes:
            print("No legacy owner_id=0 notes found. Nothing to do.")
            return

        print(f"Found {len(notes)} note(s) with owner_id=0:")
        for n in notes:
            print(f"  [{n.id}] {n.title!r:60s}  folder={n.folder}")

        if dry_run:
            print(f"\nDRY RUN — would reassign {len(notes)} note(s) to user {target_user_id} ({target_user.username}).")
            return

        # Apply update
        ids = [n.id for n in notes]
        await session.execute(
            update(Note).where(Note.id.in_(ids)).values(owner_id=target_user_id)
        )
        await session.commit()
        print(f"\n✓ Reassigned {len(notes)} note(s) to user {target_user_id} ({target_user.username}).")

    await engine.dispose()


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Reassign legacy owner_id=0 notes to a real user."
    )
    parser.add_argument(
        "--target-user", type=int, required=True,
        help="Database id of the user who will own the migrated notes."
    )
    parser.add_argument(
        "--folder", type=str, default=None,
        help="Optionally restrict migration to notes in this folder."
    )
    parser.add_argument(
        "--dry-run", action="store_true",
        help="Print what would change without writing to the database."
    )
    args = parser.parse_args()
    asyncio.run(run(args.target_user, args.folder, args.dry_run))


if __name__ == "__main__":
    main()
