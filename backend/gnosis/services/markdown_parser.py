"""Markdown parser service.

Handles:
- Parsing .md files: extract YAML frontmatter + body
- Extracting [[WikiLink]] references from body text
- Rendering Markdown body to HTML
- Writing note data back to .md file (round-trip)
- Generating timestamp-based note IDs
"""

import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import frontmatter  # python-frontmatter
import mistune
from python_slugify import slugify  # type: ignore[import-untyped]

# Regex to extract [[WikiLink]] and [[WikiLink|Alias]] patterns
WIKILINK_RE = re.compile(r"\[\[([^\[\]|]+)(?:\|[^\[\]]+)?\]\]")

# Renderer instance (thread-safe; reuse)
_renderer = mistune.create_markdown(
    plugins=["strikethrough", "footnotes", "table", "task_lists"],
)


def generate_note_id(dt: datetime | None = None) -> str:
    """Generate a timestamp-based note ID (YYYYMMDD-HHmmss).

    Args:
        dt: Datetime to use. Defaults to UTC now.

    Returns:
        Note ID string, e.g. '20260619-143022'.
    """
    if dt is None:
        dt = datetime.now(timezone.utc)
    return dt.strftime("%Y%m%d-%H%M%S")


def parse_note_file(path: Path) -> dict[str, Any]:
    """Parse a Markdown file and return a dict of note fields.

    Args:
        path: Absolute path to the .md file.

    Returns:
        Dict with keys: id, title, body, body_html, note_type, status,
        folder, tags, source_url, frontmatter, wikilinks, word_count,
        created_at, modified_at, last_reviewed.
    """
    raw = path.read_text(encoding="utf-8")
    post = frontmatter.loads(raw)

    fm: dict[str, Any] = dict(post.metadata)
    body: str = post.content

    # Derive folder from path (first path component after vault root)
    folder = path.parent.name if path.parent.name else "00-inbox"

    # Extract or generate note ID
    note_id: str = str(fm.get("id", generate_note_id()))

    title: str = str(fm.get("title") or path.stem)
    note_type: str = str(fm.get("type", "permanent"))
    status: str = str(fm.get("status", "draft"))
    tags: list[str] = [str(t) for t in (fm.get("tags") or [])]
    source_url: str | None = fm.get("source") or fm.get("source_url") or None
    last_reviewed = fm.get("last_reviewed")

    # Render HTML
    body_html: str = str(_renderer(body))

    # Extract wikilinks
    wikilinks = extract_wikilinks(body)

    # Word count (simple whitespace split)
    word_count = len(body.split())

    # Timestamps
    created_at = fm.get("created")
    modified_at = fm.get("modified")

    return {
        "id": note_id,
        "title": title,
        "slug": slugify(title),
        "body": body,
        "body_html": body_html,
        "note_type": note_type,
        "status": status,
        "folder": folder,
        "tags": tags,
        "source_url": source_url,
        "last_reviewed": last_reviewed,
        "frontmatter": fm,
        "wikilinks": wikilinks,
        "word_count": word_count,
        "created_at": created_at,
        "modified_at": modified_at,
    }


def extract_wikilinks(body: str) -> list[str]:
    """Extract all [[WikiLink]] targets from a Markdown body.

    Handles both [[Title]] and [[Title|Alias]] formats.
    Returns the target title (not the alias).

    Args:
        body: Raw Markdown text.

    Returns:
        List of unique wikilink target titles.
    """
    return list(dict.fromkeys(WIKILINK_RE.findall(body)))


def write_note_file(path: Path, title: str, body: str, fm: dict[str, Any]) -> None:
    """Write a note to a Markdown file with YAML frontmatter.

    Args:
        path: Absolute path to write the .md file.
        title: Note title (written into frontmatter).
        body: Markdown body content.
        fm: Frontmatter dict (merged with title).
    """
    fm["title"] = title
    post = frontmatter.Post(body, **fm)
    content = frontmatter.dumps(post)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def build_default_frontmatter(
    note_id: str,
    title: str,
    note_type: str = "permanent",
    status: str = "draft",
    tags: list[str] | None = None,
    source_url: str | None = None,
) -> dict[str, Any]:
    """Build the default YAML frontmatter dict for a new note.

    Args:
        note_id: Timestamp-based note ID.
        title: Note title.
        note_type: One of the standard Gnosis note types.
        status: draft | in-progress | evergreen.
        tags: List of tag strings.
        source_url: Optional source URL or citation key.

    Returns:
        Frontmatter dict ready to be passed to write_note_file.
    """
    now = datetime.now(timezone.utc).isoformat()
    return {
        "id": note_id,
        "title": title,
        "type": note_type,
        "status": status,
        "tags": tags or [],
        "created": now,
        "modified": now,
        "source": source_url or "",
        "links": [],
        "last_reviewed": None,
    }
