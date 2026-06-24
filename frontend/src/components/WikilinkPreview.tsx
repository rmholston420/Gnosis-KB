/**
 * WikilinkPreview
 * ================
 * Renders Markdown with full [[wikilink]] support:
 *
 *   [[Note Title]]          → teal link; navigates to /notes/:id on click
 *   [[Note Title|alias]]    → same but shows "alias"
 *   [[Missing Title]]       → dashed-underline "ghost" link; click → create note
 *
 * Hover over a resolved link → WikilinkPopup floating preview card.
 * Click a broken link → navigate to /notes/new?title=Missing+Title
 *
 * Uses marked v12 API: new Marked() + use({ extensions: [...] })
 */

import { useCallback, useMemo, useRef, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { Marked, type MarkedExtension, type TokenizerExtension, type RendererExtension } from 'marked';
import DOMPurify from 'dompurify';
import type { NoteListItem } from '../types';
import WikilinkPopup, { type PopupState } from './WikilinkPopup';

// ---------------------------------------------------------------------------
// Wikilink token
// ---------------------------------------------------------------------------
interface WikiToken {
  type: 'wikilink';
  raw: string;
  target: string;
  label: string;
}

// ---------------------------------------------------------------------------
// marked v12 extension factory
// ---------------------------------------------------------------------------
function buildWikilinkExtension(
  notesByTitle: Map<string, NoteListItem>,
): MarkedExtension {
  const tokenizer: TokenizerExtension = {
    name: 'wikilink',
    level: 'inline',
    start(src: string) {
      return src.indexOf('[[');
    },
    tokenizer(src: string): WikiToken | undefined {
      const match = src.match(/^\[\[([^[\]]+?)(?:\|([^[\]]+?))?\]\]/);
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
        return `<a
          class="wikilink wikilink-exists"
          data-note-id="${note.id}"
          data-note-title="${escapeHtml(t.target)}"
          href="#"
          title="${escapeHtml(t.target)}"
        >${escapeHtml(t.label)}</a>`;
      }
      return `<a
        class="wikilink wikilink-broken"
        data-note-title="${escapeHtml(t.target)}"
        href="#"
        title="Create note: ${escapeHtml(t.target)}"
      >${escapeHtml(t.label)}</a>`;
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
  body: string;
  notes: NoteListItem[];
  className?: string;
}

export default function WikilinkPreview({
  body,
  notes,
  className = '',
}: WikilinkPreviewProps) {
  const navigate = useNavigate();
  const containerRef = useRef<HTMLDivElement>(null);
  const hideTimerRef = useRef<ReturnType<typeof setTimeout> | undefined>(undefined);
  const [popup, setPopup] = useState<PopupState | null>(null);

  // Case-insensitive title → NoteListItem map
  const notesByTitle = useMemo(() => {
    const map = new Map<string, NoteListItem>();
    for (const n of notes) map.set(n.title.toLowerCase(), n);
    return map;
  }, [notes]);

  // Render Markdown → HTML with wikilink extension (memoised)
  const html = useMemo(() => {
    const instance = new Marked();
    instance.use(buildWikilinkExtension(notesByTitle));
    const raw = instance.parse(body) as string;
  return DOMPurify.sanitize(raw, { ADD_ATTR: ['data-note-id', 'data-note-title'] });
  }, [body, notesByTitle]);

  // ---- Event delegation ------------------------------------------------

  const scheduleHide = useCallback(() => {
    hideTimerRef.current = setTimeout(() => setPopup(null), 200);
  }, []);

  const cancelHide = useCallback(() => {
    if (hideTimerRef.current) clearTimeout(hideTimerRef.current);
  }, []);

  function handleClick(e: React.MouseEvent<HTMLDivElement>) {
    const target = e.target as HTMLElement;
    const anchor = target.closest('a.wikilink');
    if (!anchor) return;
    e.preventDefault();

    if (anchor.classList.contains('wikilink-exists')) {
      const id = (anchor as HTMLElement).dataset.noteId;
      if (id) navigate(`/notes/${id}`);
    } else if (anchor.classList.contains('wikilink-broken')) {
      const title = (anchor as HTMLElement).dataset.noteTitle ?? '';
      navigate(`/notes/new?title=${encodeURIComponent(title)}`);
    }
  }

  function handleMouseOver(e: React.MouseEvent<HTMLDivElement>) {
    const target = e.target as HTMLElement;
    const anchor = target.closest('a.wikilink-exists') as HTMLElement | null;
    if (!anchor) return;

    cancelHide();
    const noteId = anchor.dataset.noteId;
    const noteTitle = anchor.dataset.noteTitle?.toLowerCase();
    const note = noteId
      ? notes.find((n) => n.id === noteId)
      : noteTitle
        ? notesByTitle.get(noteTitle)
        : undefined;

    if (!note) return;
    const anchorRect = anchor.getBoundingClientRect();
    setPopup({ note, anchorRect });
  }

  function handleMouseOut(e: React.MouseEvent<HTMLDivElement>) {
    const related = e.relatedTarget as HTMLElement | null;
    if (related?.closest('.wikilink-popup')) return;
    scheduleHide();
  }

  return (
    <>
      <div
        ref={containerRef}
        className={`gnosis-prose max-w-prose mx-auto ${className}`}
        // biome-ignore lint/security/noDangerouslySetInnerHtml: sanitised by marked
        dangerouslySetInnerHTML={{ __html: html }}
        onClick={handleClick}
        onMouseOver={handleMouseOver}
        onMouseOut={handleMouseOut}
      />
      <WikilinkPopup
        state={popup}
        onClose={scheduleHide}
      />
    </>
  );
}
