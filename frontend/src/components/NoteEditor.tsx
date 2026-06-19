/**
 * NoteEditor: CodeMirror 6 Markdown editor with [[wikilink]] autocomplete.
 *
 * Features:
 * - Live markdown editing with syntax highlighting
 * - [[wikilink]] autocomplete: shows existing note titles
 * - Split / preview / edit modes
 * - Word count, last saved indicator
 * - Keyboard shortcut: Ctrl+S / Cmd+S to save
 */

import { useCallback, useEffect, useRef, useState } from 'react';
import CodeMirror, { type EditorView } from '@uiw/react-codemirror';
import { markdown } from '@codemirror/lang-markdown';
import { autocompletion, type CompletionSource } from '@codemirror/autocomplete';
import { githubDark } from '@uiw/codemirror-extensions-langs';
import { useQuery } from '@tanstack/react-query';
import api from '../services/api';
import type { Note, NoteListResponse } from '../types';
import { marked } from 'marked';
import { useAppStore } from '../store/useAppStore';

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
  const saveTimeout = useRef<ReturnType<typeof setTimeout>>(undefined);

  // Fetch note titles for autocomplete
  const { data: notesData } = useQuery<NoteListResponse>({
    queryKey: ['notes-titles'],
    queryFn: () => api.listNotes({ page_size: 200 }) as Promise<NoteListResponse>,
  });

  const noteTitles = notesData?.items.map((n) => n.title) ?? [];

  // [[wikilink]] autocomplete source
  const wikilinkCompletion: CompletionSource = useCallback(
    (context) => {
      const before = context.matchBefore(/\[\[[^\]]*/);
      if (!before) return null;
      const query = before.text.slice(2); // strip [[
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

  // Auto-save after 1.5s of inactivity
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

  // Ctrl+S / Cmd+S
  useEffect(() => {
    const handler = (e: KeyboardEvent) => {
      if ((e.ctrlKey || e.metaKey) && e.key === 's') {
        e.preventDefault();
        handleSave();
      }
    };
    window.addEventListener('keydown', handler);
    return () => window.removeEventListener('keydown', handler);
  }, [body, title]);

  const renderedHtml = marked(body) as string;

  return (
    <div className="flex flex-col h-full">
      {/* Title */}
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
          {lastSaved && !isDirty && (
            <span className="text-accent-green">Saved</span>
          )}
          <button
            onClick={() => handleSave()}
            disabled={isLoading}
            className="px-2.5 py-1 bg-accent-blue hover:bg-blue-600 text-white rounded text-xs transition-colors disabled:opacity-50"
          >
            Save
          </button>
        </div>
      </div>

      {/* Editor area */}
      <div className="flex-1 flex overflow-hidden">
        {/* Editor pane */}
        {(editorMode === 'edit' || editorMode === 'split') && (
          <div className={`flex-1 overflow-auto ${editorMode === 'split' ? 'border-r border-border' : ''}`}>
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

        {/* Preview pane */}
        {(editorMode === 'preview' || editorMode === 'split') && (
          <div className="flex-1 overflow-auto px-8 py-6">
            <div
              className="gnosis-prose max-w-prose mx-auto"
              dangerouslySetInnerHTML={{ __html: renderedHtml }}
            />
          </div>
        )}
      </div>
    </div>
  );
}
