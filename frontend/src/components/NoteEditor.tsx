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
 * textareaRef   Ref?        Attached to CM wrapper for WikilinkAutocomplete
 */

import { useCallback, useEffect, useRef, useState } from 'react';
import React from 'react';
import { useSearchParams } from 'react-router-dom';
import CodeMirror from '@uiw/react-codemirror';
import { markdown } from '@codemirror/lang-markdown';
import { autocompletion, type CompletionSource } from '@codemirror/autocomplete';
import { useQuery } from '@tanstack/react-query';
import { githubDark } from '@uiw/codemirror-theme-github';
import api from '../services/api';
import type { Note, NoteListItem, NoteListResponse } from '../types';
import { useAppStore } from '../store/useAppStore';
import WikilinkPreview from './WikilinkPreview';
import BacklinkPanel from './BacklinkPanel';
import TagInput from './TagInput';

interface NoteEditorProps {
  note: Note;
  /** Called with (body, title, tags) on every debounced save and title-blur. */
  onSave: (body: string, title?: string, tags?: string[]) => Promise<void>;
  isLoading?: boolean;
  /** Mirror every body change to parent (used by wikilink detector). */
  onBodyChange?: (value: string) => void;
  /**
   * Ref attached to the CM wrapper div so the parent can position
   * WikilinkAutocomplete relative to the editor area.
   * Note: CM6 uses a contenteditable, not a <textarea>.
   */
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
  const { editorMode, setEditorMode } = useAppStore();

  const prefillTitle = searchParams.get('title') ?? '';

  const [body,     setBody]     = useState(note.body);
  const [title,    setTitle]    = useState(note.title || prefillTitle);
  // Option C: tags live in editor state alongside body/title
  const [tags,     setTags]     = useState<string[]>(note.tags ?? []);
  const [isDirty,  setIsDirty]  = useState(!!prefillTitle && !note.id);
  const [lastSaved,setLastSaved]= useState<Date | null>(null);
  const saveTimeout = useRef<ReturnType<typeof setTimeout> | undefined>(undefined);

  // Sync state when the note being edited changes (navigation between notes)
  useEffect(() => {
    setBody(note.body);
    setTitle(note.title || prefillTitle);
    setTags(note.tags ?? []);
    setIsDirty(false);
  }, [note.id, note.body, note.title, note.tags, prefillTitle]);

  // ── Note-titles for [[wikilink]] autocomplete ───────────────────────────
  const { data: notesData } = useQuery<NoteListResponse>({
    queryKey: ['notes-titles'],
    queryFn: () => api.listNotes({ page_size: 200 }) as Promise<NoteListResponse>,
  });
  const noteList: NoteListItem[] = notesData?.items ?? [];
  const noteTitles = noteList.map((n) => n.title);

  const noteTitlesById = useCallback(
    () => new Map(noteList.map((n) => [n.id, n.title])),
    [noteList],
  );

  // ── CodeMirror wikilink completion source ──────────────────────────────
  const wikilinkCompletion: CompletionSource = useCallback(
    (context) => {
      const before = context.matchBefore(/\[\[[^\]]*/
);
      if (!before) return null;
      const query = before.text.slice(2);
      return {
        from: before.from + 2,
        options: noteTitles
          .filter((t) => t.toLowerCase().includes(query.toLowerCase()))
          .map((t) => ({ label: t, apply: `${t}]]` })),
        validFor: /^[^\]]*$/,
      };
    },
    [noteTitles],
  );

  // ── Shared save trigger ─────────────────────────────────────────────────
  /**
   * Executes the debounced save.  Accepts optional overrides so callers
   * can pass the very latest value without waiting for state to flush.
   */
  const triggerSave = useCallback(
    async (latestBody: string, latestTitle: string, latestTags: string[]) => {
      try {
        await onSave(latestBody, latestTitle, latestTags);
        setLastSaved(new Date());
        setIsDirty(false);
      } catch {
        // Silent — dirty indicator stays set
      }
    },
    [onSave],
  );

  // ── Body changes (debounced 800 ms) ─────────────────────────────────────
  const handleBodyChange = (value: string) => {
    setBody(value);
    setIsDirty(true);
    onBodyChange?.(value);
    if (saveTimeout.current) clearTimeout(saveTimeout.current);
    saveTimeout.current = setTimeout(() => triggerSave(value, title, tags), 800);
  };

  // ── Title blur ──────────────────────────────────────────────────────────
  const handleTitleBlur = async () => {
    if (isDirty) {
      await triggerSave(body, title, tags);
    }
  };

  // ── Tag changes: mark dirty + reschedule debounced save ─────────────────
  const handleTagsChange = (newTags: string[]) => {
    setTags(newTags);
    setIsDirty(true);
    if (saveTimeout.current) clearTimeout(saveTimeout.current);
    saveTimeout.current = setTimeout(() => triggerSave(body, title, newTags), 800);
  };

  // Cleanup on unmount
  useEffect(() => () => {
    if (saveTimeout.current) clearTimeout(saveTimeout.current);
  }, []);

  const showEditor  = editorMode === 'edit'  || editorMode === 'split';
  const showPreview = editorMode === 'preview' || editorMode === 'split';

  return (
    <div className="h-full flex flex-col overflow-hidden">

      {/* ── Toolbar ───────────────────────────────────────────────────── */}
      <div className="flex items-center justify-between px-4 py-2 border-b border-border flex-shrink-0 bg-bg-primary">
        <input
          type="text"
          value={title}
          onChange={(e) => { setTitle(e.target.value); setIsDirty(true); }}
          onBlur={handleTitleBlur}
          placeholder="Note title…"
          className="flex-1 bg-transparent text-text-primary text-base font-medium outline-none placeholder-text-muted mr-4 min-w-0"
        />
        <div className="flex items-center gap-3 flex-shrink-0">
          <span className="text-xs text-text-muted">
            {isLoading
              ? 'Saving…'
              : isDirty
                ? '● unsaved'
                : lastSaved
                  ? `Saved ${lastSaved.toLocaleTimeString()}`
                  : ''}
          </span>
          <div className="flex rounded border border-border overflow-hidden text-xs">
            {(['edit', 'split', 'preview'] as const).map((mode) => (
              <button
                key={mode}
                onClick={() => setEditorMode(mode)}
                className={`px-2.5 py-1 capitalize transition-colors ${
                  editorMode === mode
                    ? 'bg-accent-cyan text-white'
                    : 'text-text-muted hover:text-text-primary hover:bg-bg-elevated'
                }`}
              >
                {mode}
              </button>
            ))}
          </div>
        </div>
      </div>

      {/* ── Tag input row ─────────────────────────────────────────────── */}
      <TagInput
        tags={tags}
        onChange={handleTagsChange}
        placeholder="Add tags (Enter or comma to confirm)…"
        disabled={!note.id && !prefillTitle}
      />

      {/* ── Editor + Preview panes ───────────────────────────────────── */}
      <div className="flex-1 flex overflow-hidden min-h-0">
        {showEditor && (
          <div
            ref={textareaRef as React.RefObject<HTMLDivElement>}
            className={`overflow-auto ${
              showPreview ? 'w-1/2 border-r border-border' : 'w-full'
            }`}
          >
            <CodeMirror
              value={body}
              onChange={handleBodyChange}
              extensions={[
                markdown(),
                autocompletion({ override: [wikilinkCompletion] }),
              ]}
              theme={githubDark}
              basicSetup={{
                lineNumbers: false,
                foldGutter: false,
                highlightActiveLine: true,
              }}
              className="h-full text-sm"
            />
          </div>
        )}

        {showPreview && (
          <div className={`overflow-auto p-6 ${ showEditor ? 'w-1/2' : 'w-full' }`}>
            <WikilinkPreview body={body} notes={noteList} />
          </div>
        )}
      </div>

      {/* ── Backlink Panel ─────────────────────────────────────────────── */}
      {note.id && (
        <div className="flex-shrink-0">
          <BacklinkPanel
            noteId={note.id}
            incomingLinks={note.incoming_links}
            outgoingLinks={note.outgoing_links}
            noteTitlesById={noteTitlesById()}
          />
        </div>
      )}
    </div>
  );
}
