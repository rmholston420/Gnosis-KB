"""Gnosis Query Language (GQL) parser and executor.

GQL is a simplified Dataview-inspired query language for filtering, sorting,
and projecting notes stored in PostgreSQL.  It intentionally avoids eval()
and raw SQL interpolation — every clause is parsed into a safe AST before
being translated into SQLAlchemy Core expressions.

Supported syntax (BNF-ish)::

    query       := from? where? sort? limit? select?
    from        := FROM <folder_prefix>          # matches notes.folder LIKE 'prefix%'
    where       := WHERE <condition> (AND <condition>)*
    condition   := <field> <op> <value>
                 | tags CONTAINS <tag_name>      # tag membership
                 | <field> > <value>             # date / numeric comparison
                 | <field> < <value>
    sort        := SORT <field> (ASC|DESC)?
    limit       := LIMIT <int>
    select      := SELECT <col1>(,<col2>)*       # columns returned; default all

Allowed fields: title, status, note_type, folder, word_count,
                created_at, modified_at, last_reviewed

Namespace contract
------------------
``execute_query()`` accepts an optional ``owner_ids: set[int]`` parameter.
When provided, the query is scoped to those user IDs via
``core.namespace.scoped_note_stmt()`` — the same helper used by all other
note-reading paths.  When ``owner_ids`` is omitted (``None``), all
non-deleted notes are visible (legacy behaviour, used by tests and internal
cron jobs that run without a user context).

Examples::

    FROM 10-zettelkasten WHERE status=draft SORT modified DESC LIMIT 20
    FROM 20-projects WHERE note_type=project AND word_count > 100 LIMIT 50
    WHERE tags CONTAINS eeg SORT created_at DESC
    FROM 00-inbox SORT modified_at DESC LIMIT 10 SELECT title,status,modified_at
"""
from __future__ import annotations

import re
import time
from dataclasses import dataclass, field
from typing import Any

from sqlalchemy import and_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from gnosis.models.note import Note
from gnosis.models.tag import Tag

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

_ALLOWED_FIELDS = {
    "title": Note.title,
    "status": Note.status,
    "note_type": Note.note_type,
    "folder": Note.folder,
    "word_count": Note.word_count,
    "created_at": Note.created_at,
    "modified_at": Note.modified_at,
    "last_reviewed": Note.last_reviewed,
}

_ALLOWED_SORT_FIELDS = set(_ALLOWED_FIELDS)
_SORT_ALIAS = {"modified": "modified_at", "created": "created_at"}

_SELECT_COLS = {
    "id",
    "title",
    "status",
    "note_type",
    "folder",
    "word_count",
    "created_at",
    "modified_at",
    "last_reviewed",
    "slug",
}


# ---------------------------------------------------------------------------
# AST dataclasses
# ---------------------------------------------------------------------------

@dataclass
class ParsedQuery:
    from_folder: str | None = None
    conditions: list[dict[str, Any]] = field(default_factory=list)
    sort_field: str = "modified_at"
    sort_dir: str = "DESC"
    limit: int = 50
    select_cols: list[str] = field(default_factory=list)


# ---------------------------------------------------------------------------
# Parser
# ---------------------------------------------------------------------------

class GQLParseError(ValueError):
    """Raised when the query string cannot be parsed."""


def _tokenise(query: str) -> list[str]:
    return re.split(r"\s+", query.strip())


def parse_query(raw: str) -> ParsedQuery:  # noqa: C901
    """Parse a GQL string into a ParsedQuery AST.

    An empty or whitespace-only string is valid and returns a ParsedQuery
    with all defaults (equivalent to: SORT modified_at DESC LIMIT 50).

    Raises GQLParseError on invalid syntax.
    """
    # Empty query → return defaults rather than raising.
    if not raw.strip():
        return ParsedQuery()

    if len(raw) > 2000:
        raise GQLParseError("Query exceeds maximum length of 2000 characters.")

    tokens = _tokenise(raw)
    result = ParsedQuery()
    i = 0

    while i < len(tokens):
        tok = tokens[i].upper()

        if tok == "FROM":
            i += 1
            if i >= len(tokens):
                raise GQLParseError("FROM requires a folder prefix argument.")
            result.from_folder = tokens[i].lower()
            i += 1

        elif tok == "WHERE":
            i += 1
            while i < len(tokens) and tokens[i].upper() not in (
                "SORT", "LIMIT", "SELECT"
            ):
                if tokens[i].upper() == "AND":
                    i += 1
                    continue
                if tokens[i].upper() == "TAGS":
                    i += 1
                    if i >= len(tokens) or tokens[i].upper() != "CONTAINS":
                        raise GQLParseError("Expected TAGS CONTAINS <tag>")
                    i += 1
                    if i >= len(tokens):
                        raise GQLParseError("TAGS CONTAINS requires a tag name")
                    result.conditions.append({"type": "tag", "tag": tokens[i].lower()})
                    i += 1
                else:
                    expr = tokens[i]
                    m = re.match(r"^(\w+)([=<>!]+)(.+)$", expr)
                    if m:
                        fname, op, val = m.group(1), m.group(2), m.group(3)
                        i += 1
                    elif i + 2 < len(tokens) and tokens[i + 1] in ("=", "<", ">", ">=", "<=", "!="):
                        fname, op, val = tokens[i], tokens[i + 1], tokens[i + 2]
                        i += 3
                    else:
                        raise GQLParseError(
                            f"Cannot parse WHERE condition at token {i!r}: {tokens[i]!r}"
                        )
                    fname = fname.lower()
                    if fname not in _ALLOWED_FIELDS:
                        raise GQLParseError(
                            f"Unknown field {fname!r}. Allowed: {sorted(_ALLOWED_FIELDS)}"
                        )
                    result.conditions.append(
                        {"type": "field", "field": fname, "op": op, "value": val}
                    )

        elif tok == "SORT":
            i += 1
            if i >= len(tokens):
                raise GQLParseError("SORT requires a field name.")
            sf = tokens[i].lower()
            sf = _SORT_ALIAS.get(sf, sf)
            if sf not in _ALLOWED_SORT_FIELDS:
                raise GQLParseError(f"Unknown sort field {sf!r}.")
            result.sort_field = sf
            i += 1
            if i < len(tokens) and tokens[i].upper() in ("ASC", "DESC"):
                result.sort_dir = tokens[i].upper()
                i += 1

        elif tok == "LIMIT":
            i += 1
            if i >= len(tokens):
                raise GQLParseError("LIMIT requires an integer argument.")
            try:
                n = int(tokens[i])
            except ValueError:
                raise GQLParseError(f"LIMIT must be an integer, got {tokens[i]!r}.")
            if not 1 <= n <= 500:
                raise GQLParseError("LIMIT must be between 1 and 500.")
            result.limit = n
            i += 1

        elif tok == "SELECT":
            i += 1
            if i >= len(tokens):
                raise GQLParseError("SELECT requires at least one column name.")
            cols_raw = tokens[i].split(",")
            cols = [c.strip().lower() for c in cols_raw if c.strip()]
            bad = [c for c in cols if c not in _SELECT_COLS]
            if bad:
                raise GQLParseError(
                    f"Unknown SELECT column(s): {bad}. Allowed: {sorted(_SELECT_COLS)}"
                )
            result.select_cols = cols
            i += 1

        else:
            raise GQLParseError(f"Unknown keyword {tokens[i]!r} at position {i}.")

    return result


# ---------------------------------------------------------------------------
# Executor
# ---------------------------------------------------------------------------

_OP_MAP = {
    "=": lambda col, val: col == val,
    "!=": lambda col, val: col != val,
    ">": lambda col, val: col > val,
    "<": lambda col, val: col < val,
    ">=": lambda col, val: col >= val,
    "<=": lambda col, val: col <= val,
}


async def execute_query(
    parsed: ParsedQuery,
    db: AsyncSession,
    owner_ids: set[int] | None = None,
) -> tuple[list[dict[str, Any]], float]:
    """Execute a ParsedQuery against the database.

    Args:
        parsed:    Validated ParsedQuery AST from ``parse_query()``.
        db:        Async SQLAlchemy session.
        owner_ids: Set of user IDs whose notes the caller may read.  When
                   provided, results are scoped to those owners (plus the
                   legacy NULL-owner sentinel) via ``scoped_note_stmt()``.
                   When ``None``, all non-deleted notes are returned
                   (backward-compatible behaviour for internal callers).

    Returns:
        Tuple of (rows, query_time_ms).
    """
    t0 = time.perf_counter()

    base = (
        select(Note)
        .options(selectinload(Note.tags))
        .where(Note.is_deleted.is_(False))
    )

    # Apply vault namespace filter when caller supplies owner context
    if owner_ids is not None:
        # Local import to avoid circular dependency at module load time
        from gnosis.core.namespace import scoped_note_stmt
        stmt = scoped_note_stmt(base, owner_ids)
    else:
        stmt = base

    # FROM clause — folder prefix filter
    if parsed.from_folder:
        stmt = stmt.where(Note.folder.ilike(f"{parsed.from_folder}%"))

    # WHERE conditions
    filters = []
    for cond in parsed.conditions:
        if cond["type"] == "tag":
            tag_sub = select(Tag.id).where(Tag.name == cond["tag"])
            from gnosis.models.tag import NoteTag
            filters.append(
                Note.id.in_(
                    select(NoteTag.note_id).where(
                        NoteTag.tag_id.in_(tag_sub)
                    )
                )
            )
        else:
            col = _ALLOWED_FIELDS[cond["field"]]
            op_fn = _OP_MAP.get(cond["op"])
            if op_fn is None:
                continue
            try:
                raw_val: Any = cond["value"]
                if cond["field"] == "word_count":
                    raw_val = int(raw_val)
            except ValueError:
                raw_val = cond["value"]
            filters.append(op_fn(col, raw_val))

    if filters:
        stmt = stmt.where(and_(*filters))

    # SORT
    sort_col = _ALLOWED_FIELDS.get(parsed.sort_field, Note.modified_at)
    if parsed.sort_dir == "ASC":
        stmt = stmt.order_by(sort_col.asc())
    else:
        stmt = stmt.order_by(sort_col.desc())

    # LIMIT
    stmt = stmt.limit(parsed.limit)

    result = await db.execute(stmt)
    notes = result.scalars().all()

    select_cols = parsed.select_cols or list(_SELECT_COLS)

    rows: list[dict[str, Any]] = []
    for note in notes:
        row: dict[str, Any] = {}
        for col in select_cols:
            if col == "tags":
                row[col] = [t.name for t in note.tags]
            else:
                val = getattr(note, col, None)
                row[col] = val.isoformat() if hasattr(val, "isoformat") else val
        rows.append(row)

    ms = round((time.perf_counter() - t0) * 1000, 2)
    return rows, ms
