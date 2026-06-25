/**
 * NotesPage
 * =========
 * Note list sidebar + editor area placeholder.
 *
 * Data layer
 * ----------
 * Calls api.listNotes / api.createNote from @/services/api directly via
 * useQuery/useMutation so that vi.mock('@/services/api', ...) in tests
 * intercepts correctly at the API layer.
 */
import { useCallback } from 'react';
import { Plus, Folder } from 'lucide-react';
import { useNavigate } from 'react-router-dom';
import {
  useQuery,
  useMutation,
  useQueryClient,
} from '@tanstack/react-query';
import { useAppStore } from '../store/useAppStore';
import api from '../services/api';
import type { Note, NoteCreate } from '../types';

export default function NotesPage() {
  const { activeFolder, activeNoteId, setActiveNoteId } = useAppStore();
  const navigate = useNavigate();
  const qc = useQueryClient();

  const params = activeFolder ? { folder: activeFolder } : {};

  const { data, isLoading } = useQuery<Note[]>({
    queryKey: ['notes', params],
    queryFn:  () =>
      (api.listNotes as (p: typeof params) => Promise<Note[] | { items: Note[] }>)(params).then(
        (res) => (Array.isArray(res) ? res : (res as { items: Note[] }).items)
      ),
  });

  const notes: Note[] = data ?? [];

  const createMutation = useMutation<Note, Error, NoteCreate>({
    mutationFn: (payload) => (api.createNote as (p: NoteCreate) => Promise<Note>)(payload),
    onSuccess:  () => qc.invalidateQueries({ queryKey: ['notes'] }),
  });

  const handleNewNote = useCallback(async () => {
    const created = await createMutation.mutateAsync({
      title: 'Untitled',
      body:  '',
      folder: activeFolder ?? undefined,
    });
    setActiveNoteId(created.id);
    navigate(`/notes/${created.id}`);
  }, [activeFolder, createMutation, setActiveNoteId, navigate]);

  return (
    <div className="flex h-full overflow-hidden">
      {/* Note list sidebar */}
      <aside className="w-64 flex-shrink-0 border-r border-gnosis-border flex flex-col bg-gnosis-surface">
        <div className="h-10 flex items-center justify-between px-3 border-b border-gnosis-border flex-shrink-0">
          <h1 className="text-xs font-semibold text-gnosis-muted uppercase tracking-wider flex items-center gap-1.5">
            <Folder size={12} />
            {activeFolder ?? 'All Notes'}
          </h1>
          <button
            onClick={() => void handleNewNote()}
            className="p-1 rounded hover:bg-gnosis-hover text-gnosis-muted hover:text-gnosis-fg transition-colors"
            title="New note"
            aria-label="New note"
          >
            <Plus size={14} />
          </button>
        </div>

        <div className="flex-1 overflow-y-auto no-scrollbar">
          {isLoading ? (
            <div className="px-3 py-4 space-y-2">
              {[...Array(6)].map((_, i) => (
                <div key={i} className="skeleton skeleton-text" />
              ))}
            </div>
          ) : notes.length === 0 ? (
            <div className="flex flex-col items-center justify-center h-40 text-gnosis-muted text-sm gap-2">
              <Folder size={24} className="opacity-40" />
              <span>No notes here yet</span>
            </div>
          ) : (
            notes.map((note) => (
              <button
                key={note.id ?? note.note_id}
                onClick={() => {
                  setActiveNoteId(note.id ?? note.note_id);
                  navigate(`/notes/${note.id ?? note.note_id}`);
                }}
                className={`w-full text-left px-3 py-2.5 border-b border-gnosis-border transition-colors ${
                  activeNoteId === (note.id ?? note.note_id)
                    ? 'bg-gnosis-hover text-gnosis-fg'
                    : 'text-gnosis-muted hover:bg-gnosis-hover hover:text-gnosis-fg'
                }`}
              >
                <p className="text-sm font-medium truncate">{note.title}</p>
                <p className="text-xs text-gnosis-muted truncate mt-0.5">
                  {note.folder ?? '\u2014'}
                </p>
              </button>
            ))
          )}
        </div>
      </aside>

      {/* Editor area placeholder */}
      <div className="flex-1 overflow-hidden">
        <div className="flex flex-col items-center justify-center h-full text-gnosis-muted gap-3">
          <BookOpenIcon />
          <p className="text-sm">Select a note or create a new one</p>
        </div>
      </div>
    </div>
  );
}

function BookOpenIcon() {
  return (
    <svg
      width="40"
      height="40"
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth="1.5"
      strokeLinecap="round"
      strokeLinejoin="round"
      className="opacity-30"
    >
      <path d="M2 3h6a4 4 0 0 1 4 4v14a3 3 0 0 0-3-3H2z" />
      <path d="M22 3h-6a4 4 0 0 0-4 4v14a3 3 0 0 1 3-3h7z" />
    </svg>
  );
}
