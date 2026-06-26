/**
 * NoteEditor
 * ==========
 * CodeMirror 6 Markdown editor with:
 *   - [[wikilink]] autocomplete (built-in CM6 completions)
 *   - Split edit/preview/both modes
 *   - Auto-save with debounce (Option C: tags included in every save)
 *   - TagInput row between toolbar and CodeMirror (new in Slice 14)
 *   - BacklinkPanel showing incoming + outgoing links
 *   - Pre-fill title from ?title= query param (for broken-link creation)
 *
 * Props
 * -----
 * note          Note        The note to edit (required)
 * onSave        function    Called with (body, title, tags) on auto-save
 * isLoading     boolean?    Shows "Saving…" in status
 * onBodyChange  function?   Mirror every body change to parent
 * textareaRef   Ref?        Attached to CM wrapper div for WikilinkAutocomplete.
 *                           Typed as HTMLDivElement — only a div is ever attached.
 *
 * Audit fixes (2026-06-25)
 * ------------------------
 * 1. noteTitlesById wrapped in useMemo — was rebuilt on every render (O(n)
 *    over up to 2000 notes on every keystroke).
 * 2. prefillTitle added to useEffect dependency array; eslint-disable removed.
 * 3. saveTimerRef cleanup on unmount prevents post-unmount onSave calls.
 * 4. handleTitleBlur wrapped in useCallback with correct deps so it no longer
 *    captures stale tags from the time the title field was focused.
 * 5. void onSave() replaced with .catch() so network failures re-flag dirty.
 * 6. textareaRef prop type narrowed to HTMLDivElement (was HTMLTextAreaElement
 *    | HTMLDivElement with a silent cast at the attachment site).
 * 7. split-mode preview pane gets min-w-[280px] for narrow viewports.
 * 8. TagInput disabled condition removed — tags are always interactive.
 */

import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import React from 'react';
import { useSearchParams } from 'react-router-dom';
import CodeMirror from '@uiw/react-codemirror';
import { markdown } from '@codemirror/lang-markdown';
import { autocompletion } from '@codemirror/autocomplete';
import { githubDark } from '@uiw/codemirror-theme-github';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import type { Note } from '../types';
import TagInput from './TagInput';
import BacklinkPanel from './BacklinkPanel';
import { useNotes } from '../hooks/useNotes';

interface NoteEditorProps {
  note: Note;
  onSave: (body: string, title: string, tags: string[]) => Promise<void>;
  isLoading?: boolean;
  onBodyChange?: (value: string) => void;
  /** Ref forwarded to the CM editor wrapper div, used by WikilinkAutocomplete. */
  textareaRef?: React.RefObject<HTMLDivElement>;
}

export default function NoteEditor({
  note,
  onSave,
  isLoading,
  onBodyChange,
  textareaRef,
}: NoteEditorProps) {
  const [searchParams] = useSearchParams();
  const prefillTitle = searchParams.get('title') ?? '';

  const [title, setTitle] = useState(note.title || prefillTitle);
  const [body,  setBody]  = useState(note.body  ?? '');
  const [tags,  setTags]  = useState<string[]>(note.tags ?? []);
  const [mode,  setMode]  = useState<'edit' | 'split' | 'preview'>('edit');
  const [isDirty, setIsDirty] = useState(false);

  const saveTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  // ---- Cleanup debounce timer on unmount ---------------------------------
  // Prevents onSave firing after the component is torn down, which would
  // trigger a React "state update on unmounted component" warning.
  useEffect(() => {
    return () => {
      if (saveTimerRef.current) clearTimeout(saveTimerRef.current);
    };
  }, []);

  // ---- Note navigation — reset when note.id or prefillTitle changes ------
  // prefillTitle must be in the dependency array; omitting it caused stale
  // title state when the query param changed while note.id stayed the same.
  useEffect(() => {
    setTitle(note.title || prefillTitle);
    setBody(note.body ?? '');
    setTags(note.tags ?? []);
    setIsDirty(false);
  }, [note.id, prefillTitle]);

  // ---- Debounced auto-save -----------------------------------------------
  const scheduleAutoSave = useCallback(
    (newBody: string, newTitle: string, newTags: string[]) => {
      if (saveTimerRef.current) clearTimeout(saveTimerRef.current);
      saveTimerRef.current = setTimeout(() => {
        onSave(newBody, newTitle, newTags).catch((err) => {
          console.error('[NoteEditor] auto-save failed', err);
          setIsDirty(true); // Re-flag dirty so the user knows the save failed
        });
        setIsDirty(false);
      }, 1500);
    },
    [onSave]
  );

  // ---- Handlers ----------------------------------------------------------
  const handleTitleChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    setTitle(e.target.value);
    setIsDirty(true);
  };

  // useCallback with full deps so the closure always sees current body/title/tags.
  // The previous non-memoized version captured stale tag state from the time
  // the title field was focused, causing blur-saves to drop recent tag edits.
  const handleTitleBlur = useCallback(() => {
    if (isDirty) {
      onSave(body, title, tags).catch((err) => {
        console.error('[NoteEditor] title-blur save failed', err);
        setIsDirty(true);
      });
      setIsDirty(false);
    }
  }, [isDirty, onSave, body, title, tags]);

  const handleBodyChange = (value: string) => {
    setBody(value);
    setIsDirty(true);
    onBodyChange?.(value);
    scheduleAutoSave(value, title, tags);
  };

  const handleTagsChange = (newTags: string[]) => {
    setTags(newTags);
    setIsDirty(true);
    scheduleAutoSave(body, title, newTags);
  };

  // ---- Note titles map for BacklinkPanel ---------------------------------
  // useMemo prevents the Map from being rebuilt on every render.
  // Previously this was a bare `new Map(...)` in the render body, which
  // performed an O(n) allocation on every keystroke across up to 2000 notes.
  const { data: allNotesData } = useNotes({ limit: 2000 });
  const noteTitlesById = useMemo(
    () => new Map((allNotesData?.items ?? []).map((n) => [n.note_id, n.title])),
    [allNotesData]
  );

  return (
    <div className="flex h-full flex-col overflow-hidden">

      {/* ── Toolbar ──────────────────────────────────────────────────────── */}
      <div className="flex items-center justify-between gap-2 border-b border-border px-3 py-1.5 flex-shrink-0">
        <input
          type="text"
          value={title}
          onChange={handleTitleChange}
          onBlur={handleTitleBlur}
          placeholder="Note title…"
          className="flex-1 bg-transparent text-sm font-semibold text-text-primary placeholder:text-text-faint focus:outline-none"
        />
        <div className="flex items-center gap-1">
          {isLoading && <span className="text-xs text-text-faint">Saving…</span>}
          {isDirty   && <span className="text-xs text-accent-orange">● unsaved</span>}
          {(['edit','split','preview'] as const).map((m) => (
            <button
              key={m}
              onClick={() => setMode(m)}
              className={`rounded px-2 py-0.5 text-xs transition-colors ${
                mode === m
                  ? 'bg-accent-teal/20 text-accent-teal'
                  : 'text-text-faint hover:text-text-primary'
              }`}
            >
              {m}
            </button>
          ))}
        </div>
      </div>

      {/* ── Tags row ─────────────────────────────────────────────────────── */}
      {/* disabled prop removed — tags are always interactive regardless of   */}
      {/* note.id presence; silently non-interactive tags with no tooltip     */}
      {/* was a poor UX on brand-new notes.                                   */}
      <div className="border-b border-border px-3 py-1 flex-shrink-0">
        <TagInput
          tags={tags}
          onChange={handleTagsChange}
        />
      </div>

      {/* ── Editor area ──────────────────────────────────────────────────── */}
      <div className="flex flex-1 min-h-0 overflow-hidden">

        {/* CodeMirror pane */}
        {(mode === 'edit' || mode === 'split') && (
          <div
            className="flex-1 min-w-0 overflow-auto"
            ref={textareaRef}
          >
            <CodeMirror
              value={body}
              onChange={handleBodyChange}
              extensions={[markdown(), autocompletion()]}
              theme={githubDark}
              basicSetup={{ lineNumbers: false, foldGutter: false }}
              className="h-full text-sm"
            />
          </div>
        )}

        {/* Preview pane */}
        {/* min-w-[280px] prevents the pane collapsing below readable width  */}
        {/* on narrow viewports (13" laptop + open sidebar).                 */}
        {(mode === 'preview' || mode === 'split') && (
          <div className={`overflow-auto p-4 ${
            mode === 'split' ? 'w-1/2 min-w-[280px] border-l border-border' : 'flex-1'
          }`}>
            <div className="prose prose-sm prose-invert max-w-none">
              <ReactMarkdown remarkPlugins={[remarkGfm]}>{body}</ReactMarkdown>
            </div>
          </div>
        )}
      </div>

      {/* ── Backlink panel ───────────────────────────────────────────────── */}
      {note.id && (
        <div className="border-t border-border flex-shrink-0">
          <BacklinkPanel
            noteId={note.id}
            incomingLinks={note.incoming_links ?? []}
            outgoingLinks={note.outgoing_links ?? []}
            noteTitlesById={noteTitlesById}
          />
        </div>
      )}
    </div>
  );
}
