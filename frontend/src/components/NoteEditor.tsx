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
import { autocompletion } from '@codemirror/autocomplete';
import { githubDark } from '@uiw/codemirror-theme-github';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import type { Note } from '../types';
import TagInput from './TagInput';
import BacklinkPanel from './BacklinkPanel';
import api from '../services/api';

interface NoteEditorProps {
  note: Note;
  onSave: (body: string, title: string, tags: string[]) => Promise<void>;
  isLoading?: boolean;
  onBodyChange?: (value: string) => void;
  /** Ref forwarded to the CM editor wrapper div, used by WikilinkAutocomplete. */
  textareaRef?: React.RefObject<HTMLTextAreaElement | HTMLDivElement>;
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

  // ---- Note navigation — reset when note.id changes ----------------------
  useEffect(() => {
    setTitle(note.title || prefillTitle);
    setBody(note.body ?? '');
    setTags(note.tags ?? []);
    setIsDirty(false);
  }, [note.id]); // eslint-disable-line react-hooks/exhaustive-deps

  // ---- Debounced auto-save -----------------------------------------------
  const scheduleAutoSave = useCallback(
    (newBody: string, newTitle: string, newTags: string[]) => {
      if (saveTimerRef.current) clearTimeout(saveTimerRef.current);
      saveTimerRef.current = setTimeout(() => {
        void onSave(newBody, newTitle, newTags);
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

  const handleTitleBlur = () => {
    if (isDirty) {
      void onSave(body, title, tags);
      setIsDirty(false);
    }
  };

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

  // ---- Wikilink note titles (for BacklinkPanel) -------------------------
  const { data: allNotesData } = {
    data: null as { items: Array<{ id: string; title: string }> } | null
  };
  // Minimal titles map for BacklinkPanel
  const noteTitlesById = new Map(
    (allNotesData?.items ?? []).map((n) => [n.id, n.title])
  );

  return (
    <div className="flex h-full flex-col overflow-hidden">

      {/* ── Toolbar ──────────────────────────────────────────────────── */}
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

      {/* ── Tags row ─────────────────────────────────────────────────── */}
      <div className="border-b border-border px-3 py-1 flex-shrink-0">
        <TagInput
          tags={tags}
          onChange={handleTagsChange}
          disabled={!note.id && !prefillTitle}
        />
      </div>

      {/* ── Editor area ──────────────────────────────────────────────── */}
      <div className="flex flex-1 min-h-0 overflow-hidden">

        {/* CodeMirror pane */}
        {(mode === 'edit' || mode === 'split') && (
          <div
            className="flex-1 min-w-0 overflow-auto"
            ref={textareaRef as React.RefObject<HTMLDivElement | HTMLTextAreaElement>}
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
        {(mode === 'preview' || mode === 'split') && (
          <div className={`overflow-auto p-4 ${
            mode === 'split' ? 'w-1/2 border-l border-border' : 'flex-1'
          }`}>
            <div className="prose prose-sm prose-invert max-w-none">
              <ReactMarkdown remarkPlugins={[remarkGfm]}>{body}</ReactMarkdown>
            </div>
          </div>
        )}
      </div>

      {/* ── Backlink panel ───────────────────────────────────────────── */}
      {note.id && (
        <div className="border-t border-border flex-shrink-0">
          <BacklinkPanel
            noteId={note.id}
            incomingLinks={note.incoming_links ?? []}
            outgoingLinks={note.outgoing_links ?? []}
            noteTitlesById={noteTitlesById}
            // Expose a way to pre-fetch title map
            onFetchTitles={async () => {
              const res = await api.listNotes({ page: 1, page_size: 500 });
              return new Map(res.items.map((n) => [n.id, n.title]));
            }}
          />
        </div>
      )}
    </div>
  );
}
