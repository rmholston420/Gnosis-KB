/**
 * WikilinkAutocomplete — floating autocomplete popup for [[wikilink]] syntax.
 *
 * Also exports useWikilinkDetector — a hook that monitors a textarea ref
 * for [[ patterns and returns the current query string + an insertWikilink helper.
 */
import React, { useEffect, useRef, useState, useCallback } from 'react';
import type { Dispatch, SetStateAction, RefObject } from 'react';
import { useQuery } from '@tanstack/react-query';
import api from '../../services/api';
import type { Note } from '../../types';

export interface WikilinkAutocompleteProps {
  query:      string;
  anchorRect: DOMRect;
  onSelect:   (title: string) => void;
  onClose:    () => void;
}

export function WikilinkAutocomplete({
  query, anchorRect, onSelect, onClose,
}: WikilinkAutocompleteProps) {
  const containerRef = useRef<HTMLDivElement>(null);

  const { data: results } = useQuery({
    queryKey: ['wikilink-autocomplete', query],
    queryFn:  () =>
      api.listNotes({ q: query, limit: 8 })
        .then((res) => (res.items ?? []) as unknown as Note[]),
    enabled:  query.trim().length > 0,
    staleTime: 10_000,
  });

  useEffect(() => {
    function handleKey(e: KeyboardEvent) {
      if (e.key === 'Escape') onClose();
    }
    document.addEventListener('keydown', handleKey);
    return () => document.removeEventListener('keydown', handleKey);
  }, [onClose]);

  useEffect(() => {
    function handleClick(e: MouseEvent) {
      if (containerRef.current && !containerRef.current.contains(e.target as Node)) {
        onClose();
      }
    }
    document.addEventListener('mousedown', handleClick);
    return () => document.removeEventListener('mousedown', handleClick);
  }, [onClose]);

  if (!results || results.length === 0) return null;

  const style: React.CSSProperties = {
    position: 'fixed',
    top:      anchorRect.bottom + 4,
    left:     anchorRect.left,
    zIndex:   9999,
  };

  return (
    <div
      ref={containerRef}
      style={style}
      className="bg-gnosis-surface border border-gnosis-border rounded shadow-lg min-w-[220px] max-w-[360px] max-h-64 overflow-y-auto"
    >
      {results.map((note: Note) => (
        <button
          key={note.note_id ?? note.id}
          type="button"
          onClick={() => onSelect(note.title)}
          className="w-full text-left px-3 py-2 text-xs text-gnosis-fg hover:bg-gnosis-border transition-colors"
        >
          <span className="font-medium">{note.title}</span>
          {note.folder && (
            <span className="ml-2 text-gnosis-muted">{note.folder}</span>
          )}
        </button>
      ))}
    </div>
  );
}

export default WikilinkAutocomplete;

// ── useWikilinkDetector ───────────────────────────────────────────────────────

export interface WikilinkDetectorResult {
  wikilinkQuery:  string;
  insertWikilink: (title: string) => void;
}

export function useWikilinkDetector(
  ref: RefObject<HTMLTextAreaElement | HTMLDivElement | null>,
  value: string,
  setValue: Dispatch<SetStateAction<string>>,
): WikilinkDetectorResult {
  const [wikilinkQuery, setWikilinkQuery] = useState('');

  useEffect(() => {
    const el = ref.current;
    if (!el) return;

    function handleInput() {
      const textarea = el as HTMLTextAreaElement;
      const pos = textarea.selectionStart ?? value.length;
      const before = value.slice(0, pos);
      const match = before.match(/\[\[([^\]]*)$/);
      setWikilinkQuery(match ? match[1] : '');
    }

    el.addEventListener('input', handleInput as EventListener);
    el.addEventListener('keyup',  handleInput as EventListener);
    return () => {
      el.removeEventListener('input', handleInput as EventListener);
      el.removeEventListener('keyup',  handleInput as EventListener);
    };
  }, [ref, value]);

  const insertWikilink = useCallback((title: string) => {
    setValue((prev) => {
      const match = prev.match(/([\s\S]*)\[\[([^\]]*)$/);
      if (!match) return prev + `[[${title}]]`;
      return match[1] + `[[${title}]]`;
    });
    setWikilinkQuery('');
  }, [setValue]);

  return { wikilinkQuery, insertWikilink };
}
