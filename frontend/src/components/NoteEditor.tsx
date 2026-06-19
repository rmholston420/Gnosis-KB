/**
 * NoteEditor
 * ==========
 * CodeMirror 6 Markdown editor with:
 *   - [[wikilink]] autocomplete
 *   - Split edit/preview/both modes
 *   - Auto-save with debounce
 *   - BacklinkPanel showing incoming + outgoing links
 *   - Pre-fill title from ?title= query param (for broken-link creation)
 */

import { useCallback, useEffect, useRef, useState } from 'react';
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

interface NoteEditorProps {
  note: Note;
  onSave: (body: string, title?: string) => Promise<void>;
  isLoading?: boolean;
}

export default function NoteEditor({ note, onSave, isLoading }: NoteEditorProps) {
  const [searchParams] = useSearchParams();
  const { editorMode, setEditorMode } = useAppStore();

  // Pre-fill title from ?title= param (broken-link creation flow)
  const prefillTitle = searchParams.get('title') ?? '';

  const [body, setBody] = useState(note.body);
  const [title, setTitle] = useState(note.title || prefillTitle);
  const [isDirty, setIsDirty] = useState(!!prefillTitle && !note.id);
  const [lastSaved, setLastSaved] = useState<Date | null>(null);
  const saveTimeout = useRef<ReturnType<typeof setTimeout> | undefined>(undefined);

  // Sync when a different note is loaded
  useEffect(() => {
    setBody(note.body);
    setTitle(note.title || prefillTitle);
    setIsDirty(false);
  }, [note.id, note.body, note.title, prefillTitle]);

  // Fetch all note list for wikilink autocomplete + preview
  const { data: notesData } = useQuery<NoteListResponse>({
    queryKey: ['notes-titles'],
    queryFn: () => api.listNotes({ page_size: 200 }) as Promise<NoteListResponse>,
  });
  const noteList: NoteListItem[] = notesData?.items ?? [];
  const noteTitles = noteList.map((n) => n.title);

  // Build id→title map for BacklinkPanel
  const noteTitlesById = useCallback(
    () => new Map(noteList.map((n) => [n.id, n.title])),
    [noteList],
  );

  // ---- Wikilink autocomplete -------------------------------------------
  const wikilinkCompletion: CompletionSource = useCallback(
    (context) => {
      const before = context.matchBefore(/\[\[[^\]]*/);
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

  // ---- Auto-save (800 ms debounce) ------------------------------------
  const handleBodyChange = (value: string) => {
    setBody(value);
    setIsDirty(true);
    if (saveTimeout.current) clearTimeout(saveTimeout.current);
    saveTimeout.current = setTimeout(async () => {
      try {
        await onSave(value, title);
        setLastSaved(new Date());
        setIsDirty(false);
      } catch {
        // Silent; dirty indicator stays
      }
    }, 800);
  };

  const handleTitleBlur = async () => {
    if (isDirty) {
      try {
        await onSave(body, title);
        setLastSaved(new Date());
        setIsDirty(false);
      } catch {
        // Silent
      }
    }
  };

  // Cleanup on unmount
  useEffect(() => () => {
    if (saveTimeout.current) clearTimeout(saveTimeout.current);
  }, []);

  const showEditor  = editorMode === 'edit'  || editorMode === 'split';
  const showPreview = editorMode === 'preview' || editorMode === 'split';

  return (
    <div className="h-full flex flex-col overflow-hidden">
      {/* ---- Toolbar ---- */}
      <div className="flex items-center justify-between px-4 py-2 border-b border-border flex-shrink-0 bg-bg-primary">
        {/* Title */}
        <input
          type="text"
          value={title}
          onChange={(e) => { setTitle(e.target.value); setIsDirty(true); }}
          onBlur={handleTitleBlur}
          placeholder="Note title…"
          className="flex-1 bg-transparent text-text-primary text-base font-medium outline-none placeholder-text-faint mr-4 min-w-0"
        />
        {/* Save indicator + mode toggle */}
        <div className="flex items-center gap-3 flex-shrink-0">
          <span className="text-xs text-text-faint">
            {isLoading ? 'Saving…' : isDirty ? '● unsaved' : lastSaved ? `Saved ${lastSaved.toLocaleTimeString()}` : ''}
          </span>
          <div className="flex rounded border border-border overflow-hidden text-xs">
            {(['edit', 'split', 'preview'] as const).map((mode) => (
              <button
                key={mode}
                onClick={() => setEditorMode(mode)}
                className={`px-2.5 py-1 capitalize transition-colors ${
                  editorMode === mode
                    ? 'bg-teal-700 text-white'
                    : 'text-text-muted hover:text-text-primary hover:bg-bg-elevated'
                }`}
              >
                {mode}
              </button>
            ))}
          </div>
        </div>
      </div>

      {/* ---- Editor + Preview panes ---- */}
      <div className="flex-1 flex overflow-hidden min-h-0">
        {showEditor && (
          <div className={`overflow-auto ${showPreview ? 'w-1/2 border-r border-border' : 'w-full'}`}>
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
          <div className={`overflow-auto p-6 ${showEditor ? 'w-1/2' : 'w-full'}`}>
            <WikilinkPreview body={body} notes={noteList} />
          </div>
        )}
      </div>

      {/* ---- Backlink Panel ---- */}
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
