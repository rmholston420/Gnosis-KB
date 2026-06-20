/**
 * WikilinkAutocomplete
 * ====================
 * Floating suggestion dropdown that appears when the user types [[ in any
 * <textarea> or CodeMirror editor.  Wire it with:
 *
 *   <WikilinkAutocomplete
 *     anchorRef={textareaRef}
 *     query={wikilinkQuery}          // text after [[ up to cursor
 *     onSelect={(note) => void}       // called with the matched NoteListItem
 *     onClose={() => void}
 *   />
 *
 * The parent must track `wikilinkQuery` by parsing the textarea value + caret
 * position (see useWikilinkDetector hook below the component).
 */

import React, { useEffect, useRef, useState, KeyboardEvent } from 'react';
import api from '../../services/api';

interface NoteListItem {
  id: string;
  title: string;
  slug: string;
  folder?: string;
}

interface Props {
  /** Ref to the textarea/editor element — used for positioning the popup. */
  anchorRef: React.RefObject<HTMLTextAreaElement | HTMLDivElement | null>;
  /** Text fragment after [[ (up to cursor). */
  query: string;
  onSelect: (note: NoteListItem) => void;
  onClose: () => void;
}

export function WikilinkAutocomplete({ anchorRef, query, onSelect, onClose }: Props) {
  const [results, setResults] = useState<NoteListItem[]>([]);
  const [activeIdx, setActiveIdx] = useState(0);
  const [loading, setLoading] = useState(false);
  const [position, setPosition] = useState({ top: 0, left: 0 });
  const listRef = useRef<HTMLUListElement | null>(null);

  // Debounced search
  useEffect(() => {
    if (!query) {
      setResults([]);
      return;
    }
    const timeout = setTimeout(async () => {
      setLoading(true);
      try {
        const res = await api.searchNoteByTitle(query) as { items: NoteListItem[] };
        setResults(res.items ?? []);
        setActiveIdx(0);
      } catch {
        setResults([]);
      } finally {
        setLoading(false);
      }
    }, 160);
    return () => clearTimeout(timeout);
  }, [query]);

  // Position popup below / near the anchor
  useEffect(() => {
    const el = anchorRef.current;
    if (!el) return;
    const rect = el.getBoundingClientRect();
    setPosition({
      top: rect.bottom + window.scrollY + 4,
      left: rect.left + window.scrollX,
    });
  }, [anchorRef, query]);

  // Keyboard navigation (Tab / Enter / Escape / Arrow)
  useEffect(() => {
    function handleKey(e: globalThis.KeyboardEvent) {
      if (e.key === 'Escape') { onClose(); return; }
      if (!results.length) return;
      if (e.key === 'ArrowDown') {
        e.preventDefault();
        setActiveIdx((i) => (i + 1) % results.length);
      } else if (e.key === 'ArrowUp') {
        e.preventDefault();
        setActiveIdx((i) => (i - 1 + results.length) % results.length);
      } else if (e.key === 'Enter' || e.key === 'Tab') {
        e.preventDefault();
        onSelect(results[activeIdx]);
      }
    }
    window.addEventListener('keydown', handleKey);
    return () => window.removeEventListener('keydown', handleKey);
  }, [results, activeIdx, onSelect, onClose]);

  if (!query && !loading) return null;

  return (
    <ul
      ref={listRef}
      role="listbox"
      style={{ top: position.top, left: position.left }}
      className="wikilink-autocomplete"
    >
      {loading && (
        <li className="wac-loading" role="option" aria-selected={false}>
          <span className="wac-spinner" />
          Searching…
        </li>
      )}
      {!loading && results.length === 0 && query && (
        <li className="wac-empty" role="option" aria-selected={false}>
          No notes matching “{query}”
        </li>
      )}
      {results.map((note, i) => (
        <li
          key={note.id}
          role="option"
          aria-selected={i === activeIdx}
          className={`wac-item ${i === activeIdx ? 'wac-item--active' : ''}`}
          onMouseEnter={() => setActiveIdx(i)}
          onClick={() => onSelect(note)}
        >
          <span className="wac-title">{note.title}</span>
          {note.folder && <span className="wac-folder">{note.folder}</span>}
        </li>
      ))}
    </ul>
  );
}

/**
 * useWikilinkDetector
 * ===================
 * Call inside a component that owns a <textarea> ref.  Returns the current
 * wikilink query string (text after [[ up to cursor) or null when no open
 * wikilink bracket exists.
 *
 * Usage:
 *   const { wikilinkQuery, insertWikilink } = useWikilinkDetector(textareaRef, value, onChange);
 */
export function useWikilinkDetector(
  ref: React.RefObject<HTMLTextAreaElement | null>,
  value: string,
  onChange: (v: string) => void
) {
  const [wikilinkQuery, setWikilinkQuery] = useState<string | null>(null);
  const [bracketStart, setBracketStart] = useState<number>(-1);

  function detectQuery() {
    const el = ref.current;
    if (!el) return;
    const pos = el.selectionStart ?? 0;
    const before = value.slice(0, pos);
    const match = before.match(/\[\[([^\]]*)$/);
    if (match) {
      setWikilinkQuery(match[1]);
      setBracketStart(pos - match[1].length - 2);
    } else {
      setWikilinkQuery(null);
      setBracketStart(-1);
    }
  }

  /** Called when the user selects a note from the autocomplete. */
  function insertWikilink(note: { title: string; id: string }) {
    const el = ref.current;
    if (!el || bracketStart < 0) return;
    const pos = el.selectionStart ?? 0;
    const before = value.slice(0, bracketStart);
    const after = value.slice(pos);
    const inserted = `[[${note.title}]]`;
    const newVal = before + inserted + after;
    onChange(newVal);
    setWikilinkQuery(null);
    setBracketStart(-1);
    // Restore focus + caret after React re-render
    requestAnimationFrame(() => {
      el.focus();
      const newPos = before.length + inserted.length;
      el.setSelectionRange(newPos, newPos);
    });
  }

  return { wikilinkQuery, detectQuery, insertWikilink, closeAutocomplete: () => setWikilinkQuery(null) };
}

export default WikilinkAutocomplete;
