import { useQuery } from '@tanstack/react-query';
import api from '../services/api';
import NoteEditor from '../components/NoteEditor';
import { useMutation, useQueryClient } from '@tanstack/react-query';
import type { Note } from '../types';
import { Loader2 } from 'lucide-react';

export default function DailyNotePage() {
  const queryClient = useQueryClient();

  const { data: note, isLoading } = useQuery<Note>({
    queryKey: ['daily-note'],
    queryFn: () => api.getDailyNote() as Promise<Note>,
  });

  const updateMutation = useMutation({
    mutationFn: ({ body, title }: { body: string; title?: string }) =>
      api.updateNote(note!.id, { body, title }) as Promise<Note>,
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ['daily-note'] }),
  });

  if (isLoading) {
    return (
      <div className="flex items-center justify-center h-64">
        <Loader2 className="animate-spin text-text-muted" size={24} />
      </div>
    );
  }

  if (!note) return null;

  return (
    <div className="h-full">
      <NoteEditor
        note={note}
        onSave={async (body, title) => updateMutation.mutateAsync({ body, title })}
        isLoading={updateMutation.isPending}
      />
    </div>
  );
}
