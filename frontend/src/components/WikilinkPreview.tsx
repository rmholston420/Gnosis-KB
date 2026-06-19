/**
 * WikilinkPreview
 * ================
 * Renders a Markdown string with [[wikilink]] support.
 *
 * - [[Note Title]]           → navigates to notes/:id by title lookup
 * - [[Note Title|alias]]     → same but displays "alias"
 * - Broken links (title not found) render with a .wikilink-broken class
 *
 * Usage:
 *   <WikilinkPreview body={note.body} notes={noteListItems} />
 *
 * The component is pure: it takes the flat note list (already fetched by
 * the parent) so it doesn’t issue its own network requests.
 */

import { useMemo } from 'react';
import { useNavigate } from 'react-router-dom';
import { marked, type TokenizerExtension, type RendererExtension } from 'marked';
import type { NoteListItem } from '../types';

// ---------------------------------------------------------------------------
// Wikilink token type
// ---------------------------------------------------------------------------
interface WikiToken {
  type: 'wikilink';
  raw: string;
  /** The title used for lookup (left side of |) */
  target: string;
  /** Display text (right side of |, or same as target) */
  label: string;
}

// ---------------------------------------------------------------------------
// Build a marked extension for [[wikilinks]]
// ---------------------------------------------------------------------------
function buildWikilinkExtension(
  notesByTitle: Map<string, NoteListItem>,
  onNavigate: (id: string) => void,
): marked.MarkedExtension {
  const tokenizer: TokenizerExtension = {
    name: 'wikilink',
    level: 'inline',
    start(src: string) {
      return src.indexOf('[[');
    },
    tokenize(src: string): WikiToken | undefined {
      const match = src.match(/^\[\[([^\]\[]+?)(?:\|([^\]\[]+?))?\]\]/);
      if (!match) return undefined;
      return {
        type: 'wikilink',
        raw: match[0],
        target: match[1].trim(),
        label: (match[2] ?? match[1]).trim(),
      };
    },
  };

  const renderer: RendererExtension = {
    name: 'wikilink',
    renderer(token) {
      const t = token as WikiToken;
      const note = notesByTitle.get(t.target.toLowerCase());
      if (note) {
        // Encode the note id into a data attribute; the click handler reads it.
        return `<a
          class="wikilink wikilink-exists"
          data-note-id="${note.id}"
          href="#"
          title="${escapeHtml(t.target)}"
        >${escapeHtml(t.label)}</a>`;
      }
      // Broken link — no note found
      return `<span
        class="wikilink wikilink-broken"
        title="Note not found: ${escapeHtml(t.target)}"
      >${escapeHtml(t.label)}</span>`;
    },
  };

  return { extensions: [tokenizer, renderer] };
}

function escapeHtml(s: string): string {
  return s
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;');
}

// ---------------------------------------------------------------------------
// Component
// ---------------------------------------------------------------------------
interface WikilinkPreviewProps {
  /** Raw Markdown body of the note being rendered */
  body: string;
  /** Flat list of all notes — used to resolve [[Title]] → id */
  notes: NoteListItem[];
  className?: string;
}

export default function WikilinkPreview({
  body,
  notes,
  className = '',
}: WikilinkPreviewProps) {
  const navigate = useNavigate();

  // Build title → NoteListItem map (case-insensitive)
  const notesByTitle = useMemo(() => {
    const map = new Map<string, NoteListItem>();
    for (const n of notes) {
      map.set(n.title.toLowerCase(), n);
    }
    return map;
  }, [notes]);

  // Render Markdown → HTML with wikilink extension
  const html = useMemo(() => {
    const markedInstance = new marked.Marked();
    markedInstance.use(
      buildWikilinkExtension(notesByTitle, (id) => navigate(`/notes/${id}`)),
    );
    return markedInstance.parse(body) as string;
  }, [body, notesByTitle, navigate]);

  // Handle clicks on rendered wikilinks via event delegation
  function handleClick(e: React.MouseEvent<HTMLDivElement>) {
    const target = e.target as HTMLElement;
    const anchor = target.closest('a.wikilink-exists');
    if (!anchor) return;
    e.preventDefault();
    const id = (anchor as HTMLElement).dataset.noteId;
    if (id) navigate(`/notes/${id}`);
  }

  return (
    <div
      className={`gnosis-prose max-w-prose mx-auto ${className}`}
      // biome-ignore lint/security/noDangerouslySetInnerHtml: sanitised by marked
      dangerouslySetInnerHTML={{ __html: html }}
      onClick={handleClick}
    />
  );
}
