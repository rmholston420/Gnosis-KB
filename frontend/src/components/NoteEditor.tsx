/**
 * NoteEditor: CodeMirror 6 Markdown editor with [[wikilink]] autocomplete
 * and click-to-navigate wikilink preview via WikilinkPreview.
 */

import { useCallback, useEffect, useRef, useState } from 'react';
import CodeMirror from '@uiw/react-codemirror';
import { markdown } from '@codemirror/lang-markdown';
import { autocompletion, type CompletionSource } from '@codemirror/autocomplete';
import { useQuery } from '@tanstack/react-query';
import api from '../services/api';
import type { Note, NoteListResponse } from '../types';
import { useAppStore } from '../store/useAppStore';
import WikilinkPreview from './WikilinkPreview';

// githubDark lives in @uiw/codemirror-theme-github, not codemirror-extensions-langs
import { githubDark } from '@uiw/codemirror-theme-github';

interface NoteEditorProps {
  note: Note;
  onSave: (body: string, title?: string) => Promise<void>;
  isLoading?: boolean;
}

export default function NoteEditor({ note, onSave, isLoading }: NoteEditorProps) {
  const { editorMode, setEditorMode } = useAppStore();
  const [body, setBody] = useState(note.body);
  const [title, setTitle] = useState(note.title);
  const [isDirty, setIsDirty] = useState(false);
  const [lastSaved, setLastSaved] = useState<Date | null>(null);
  const saveTimeout = useRef<ReturnType<typeof setTimeout> | undefined>(undefined);

  // Fetch all note titles for wikilink autocomplete + preview resolution
  const { data: notesData } = useQuery<NoteListResponse>({
    queryKey: ['notes-titles'],
    queryFn: () => api.listNotes({ page_size: 200 }) as Promise<NoteListResponse>,
  });

  const noteList = notesData?.items ?? [];
  const noteTitles = noteList.map((n) => n.title);

  // ---- CodeMirror wikilink autocomplete -----------------------------------
  const wikilinkCompletion: CompletionSource = useCallback(
    (context) => {
      const before = context.matchBefore(/\[\[[^\]]*/)
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
    [noteTitles]
  );

  // ---- Auto-save ----------------------------------------------------------
  const handleBodyChange = (value: string) => {
    setBody(value);
    setIsDirty(true);
    clearTimeout(saveTimeout.current);
    saveTimeout.current = setTimeout(async () => {
      await handleSave(value, title);
    }, 1500);
  };

  const handleSave = async (bodyToSave = body, titleToSave = title) => {
    await onSave(bodyToSave, titleToSave);
    setIsDirty(false);
    setLastSaved(new Date());
  };

  // ---- Cmd/Ctrl+S ---------------------------------------------------------
  useEffect(() => {
    const handler = (e: KeyboardEvent) => {
      if ((e.ctrlKey || e.metaKey) && e.key === 's') {
        e.preventDefault();
        handleSave();
      }
    };
    window.addEventListener('keydown', handler);
    return () => window.removeEventListener('keydown', handler);
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [body, title]);

  return (
    <div className="flex flex-col h-full">
      {/* Title bar */}
      <div className="px-6 pt-4 pb-2 border-b border-border flex-shrink-0">
        <input
          type="text"
          value={title}
          onChange={(e) => { setTitle(e.target.value); setIsDirty(true); }}
          className="w-full bg-transparent text-2xl font-semibold text-text-primary outline-none placeholder-text-muted"
          placeholder="Note title..."
        />
      </div>

      {/* Toolbar */}
      <div className="flex items-center justify-between px-4 py-1.5 border-b border-border bg-bg-secondary flex-shrink-0">
        <div className="flex items-center gap-1">
          {(['edit', 'split', 'preview'] as const).map((mode) => (
            <button
              key={mode}
              onClick={() => setEditorMode(mode)}
              className={`px-2.5 py-1 text-xs rounded capitalize transition-colors ${
                editorMode === mode
                  ? 'bg-bg-elevated text-text-primary'
                  : 'text-text-secondary hover:text-text-primary'
              }`}
            >
              {mode}
            </button>
          ))}
        </div>
        <div className="flex items-center gap-3 text-xs text-text-muted">
          <span>{body.split(/\s+/).filter(Boolean).length}w</span>
          {isDirty && <span className="text-accent-orange">Unsaved</span>}
          {lastSaved && !isDirty && <span className="text-accent-green">Saved</span>}
          <button
            onClick={() => handleSave()}
            disabled={isLoading}
            className="px-2.5 py-1 bg-accent-blue hover:bg-blue-600 text-white rounded text-xs transition-colors disabled:opacity-50"
          >
            Save
          </button>
        </div>
      </div>

      {/* Editor + Preview panes */}
      <div className="flex-1 flex overflow-hidden">
        {(editorMode === 'edit' || editorMode === 'split') && (
          <div className={`flex-1 overflow-auto ${
            editorMode === 'split' ? 'border-r border-border' : ''
          }`}>
            <CodeMirror
              value={body}
              theme={githubDark}
              extensions={[
                markdown(),
                autocompletion({ override: [wikilinkCompletion] }),
              ]}
              onChange={handleBodyChange}
              className="h-full text-sm"
              basicSetup={{
                lineNumbers: false,
                foldGutter: false,
                highlightActiveLine: true,
              }}
            />
          </div>
        )}

        {(editorMode === 'preview' || editorMode === 'split') && (
          <div className="flex-1 overflow-auto px-8 py-6">
            {/*
              WikilinkPreview replaces the raw marked() call.
              It resolves [[Title]] → notes/:id and navigates on click.
            */}
            <WikilinkPreview body={body} notes={noteList} />
          </div>
        )}
      </div>
    </div>
  );
}
