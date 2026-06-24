/**
 * WikilinkAutocomplete
 * ====================
 * Floating dropdown that appears while typing [[...]] in the note editor.
 *
 * Behaviour:
 *  - Detects when the cursor is inside an open [[  ]] wikilink token.
 *  - Fetches /api/v1/notes/?search=<query> to get matching notes.
 *  - Renders a floating list anchored below the cursor.
 *  - Arrow keys navigate, Enter/Tab inserts, Escape closes.
 *  - Clicking an item inserts the full [[Note Title]] token.
 *
 * The component is kept thin — all cursor/caret detection lives in the
 * position (see useWikilinkDetector hook below the component).
 */

import React, { useEffect, useRef, useState } from 'react';
import api from '../../services/api';

interface NoteListItem {
  id: string;
  title: string;
}

interface WikilinkAutocompleteProps {
  query: string;           // Text typed after [[
  anchorRect: DOMRect;     // Bounding rect of [[ token for positioning
  onSelect: (title: string) => void;
  onClose: () => void;
}

export default function WikilinkAutocomplete({
  query,
  anchorRect,
  onSelect,
  onClose,
}: WikilinkAutocompleteProps) {
  const [items,       setItems]       = useState<NoteListItem[]>([]);
  const [activeIndex, setActiveIndex] = useState(0);
  const listRef = useRef<HTMLUListElement>(null);

  // Fetch matching notes
  useEffect(() => {
    if (!query && query !== '') { setItems([]); return; }
    let cancelled = false;
    api.listNotes({ search: query, limit: 8 })
      .then((res) => {
        if (!cancelled) {
          const notes = (res as { items?: NoteListItem[]; data?: NoteListItem[] } | NoteListItem[]);
          if (Array.isArray(notes)) setItems(notes);
          else if (notes.items) setItems(notes.items);
          else if (notes.data) setItems(notes.data);
        }
      })
      .catch(() => {});
    return () => { cancelled = true; };
  }, [query]);

  // Keyboard navigation
  useEffect(() => {
    function handleKey(e: globalThis.KeyboardEvent) {
      if (e.key === 'ArrowDown') {
        e.preventDefault();
        setActiveIndex((i) => Math.min(i + 1, items.length - 1));
      } else if (e.key === 'ArrowUp') {
        e.preventDefault();
        setActiveIndex((i) => Math.max(i - 1, 0));
      } else if (e.key === 'Enter' || e.key === 'Tab') {
        e.preventDefault();
        if (items[activeIndex]) onSelect(items[activeIndex].title);
      } else if (e.key === 'Escape') {
        e.preventDefault();
        onClose();
      }
    }
    window.addEventListener('keydown', handleKey);
    return () => window.removeEventListener('keydown', handleKey);
  }, [items, activeIndex, onSelect, onClose]);

  if (items.length === 0) return null;

  // Position below anchor
  const top  = anchorRect.bottom + window.scrollY + 4;
  const left = anchorRect.left   + window.scrollX;

  return (
    <ul
      ref={listRef}
      role="listbox"
      style={{
        position: 'absolute',
        top,
        left,
        zIndex: 9999,
        minWidth: 220,
        maxWidth: 360,
        maxHeight: 240,
        overflowY: 'auto',
      }}
      className="rounded-lg border border-border-default bg-bg-elevated shadow-lg py-1"
    >
      {items.map((item, i) => (
        <li
          key={item.id}
          role="option"
          aria-selected={i === activeIndex}
          onClick={() => onSelect(item.title)}
          className={`px-3 py-1.5 text-sm cursor-pointer ${
            i === activeIndex
              ? 'bg-bg-tertiary text-text-primary'
              : 'text-text-muted hover:bg-bg-tertiary hover:text-text-primary'
          }`}
        >
          {item.title}
        </li>
      ))}
    </ul>
  );
}

/**
 * useWikilinkDetector
 *
 * Detects when the textarea cursor is inside an open [[ token and returns
 * the current query string + bounding rect for the autocomplete dropdown.
 *
 * Usage:
 *   const { wikilinkQuery, insertWikilink } = useWikilinkDetector(textareaRef, value, onChange);
 */
// eslint-disable-next-line react-refresh/only-export-components
export function useWikilinkDetector(
  ref: React.RefObject<HTMLTextAreaElement | null>,
  value: string,
  onChange: (v: string) => void
) {
  const [wikilinkQuery, setWikilinkQuery] = useState<string | null>(null);
  const [anchorRect,    setAnchorRect]    = useState<DOMRect | null>(null);

  useEffect(() => {
    const el = ref.current;
    if (!el) return;

    function detectWikilink() {
      if (!el) return;
      const pos  = el.selectionStart ?? 0;
      const text = el.value.slice(0, pos);
      const match = text.match(/\[\[([^\][]*)$/);
      if (match) {
        setWikilinkQuery(match[1]);
        // Get caret rect
        const rect = el.getBoundingClientRect();
        setAnchorRect(new DOMRect(rect.left, rect.bottom, 0, 0));
      } else {
        setWikilinkQuery(null);
        setAnchorRect(null);
      }
    }

    el.addEventListener('keyup', detectWikilink);
    el.addEventListener('click', detectWikilink);
    return () => {
      el.removeEventListener('keyup', detectWikilink);
      el.removeEventListener('click', detectWikilink);
    };
  }, [ref]);

  function insertWikilink(title: string) {
    const el = ref.current;
    if (!el) return;
    const pos   = el.selectionStart ?? 0;
    const text  = el.value;
    const before = text.slice(0, pos);
    const after  = text.slice(pos);
    const openIdx = before.lastIndexOf('[[');
    if (openIdx === -1) return;
    const newValue = before.slice(0, openIdx) + `[[${title}]]` + after;
    onChange(newValue);
    setWikilinkQuery(null);
    setAnchorRect(null);
    // Move cursor after the inserted wikilink
    requestAnimationFrame(() => {
      const newPos = openIdx + title.length + 4; // [[  ]] = 4 chars
      el.setSelectionRange(newPos, newPos);
      el.focus();
    });
  }

  return { wikilinkQuery, anchorRect, insertWikilink };
}
