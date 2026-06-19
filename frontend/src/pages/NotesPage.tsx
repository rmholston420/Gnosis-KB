import { useQuery } from '@tanstack/react-query';
import { useAppStore } from '../store/useAppStore';
import NoteCard from '../components/NoteCard';
import api from '../services/api';
import type { NoteListResponse } from '../types';
import { Loader2 } from 'lucide-react';

export default function NotesPage() {
  const { activeFolder, activeNoteId } = useAppStore();

  const { data, isLoading, error } = useQuery<NoteListResponse>({
    queryKey: ['notes', activeFolder],
    queryFn: () =>
      api.listNotes(activeFolder ? { folder: activeFolder, page_size: 100 } : { page_size: 100 }) as Promise<NoteListResponse>,
  });

  if (isLoading) {
    return (
      <div className="flex items-center justify-center h-64">
        <Loader2 className="animate-spin text-text-muted" size={24} />
      </div>
    );
  }

  if (error) {
    return (
      <div className="p-6 text-accent-red text-sm">
        Error loading notes: {(error as Error).message}
      </div>
    );
  }

  return (
    <div className="p-4">
      <div className="flex items-center justify-between mb-4">
        <h1 className="text-lg font-semibold text-text-primary">
          {activeFolder ? activeFolder.replace(/^\d+-/, '') : 'All Notes'}
        </h1>
        <span className="text-xs text-text-muted">{data?.total ?? 0} notes</span>
      </div>
      <div className="space-y-1.5">
        {data?.items.map((note) => (
          <NoteCard key={note.id} note={note} active={note.id === activeNoteId} />
        ))}
        {data?.items.length === 0 && (
          <p className="text-text-muted text-sm text-center py-12">No notes yet. Create your first note!</p>
        )}
      </div>
    </div>
  );
}
