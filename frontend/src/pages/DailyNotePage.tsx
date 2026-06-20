import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import api from '../services/api';
import NoteEditor from '../components/NoteEditor';
import type { Note } from '../types';
import { Loader2, CalendarDays } from 'lucide-react';

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

  const today = new Date().toLocaleDateString('en-US', {
    weekday: 'long', year: 'numeric', month: 'long', day: 'numeric',
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
    <div className="h-full flex flex-col">
      <div className="flex items-center gap-2 px-4 py-2 border-b border-border flex-shrink-0 bg-bg-primary">
        <CalendarDays size={15} className="text-text-muted" />
        <span className="text-xs font-medium text-text-muted">{today}</span>
      </div>
      <div className="flex-1 overflow-hidden">
        <NoteEditor
          note={note}
          onSave={async (body, title) => {
            await updateMutation.mutateAsync({ body, title });
          }}
          isLoading={updateMutation.isPending}
        />
      </div>
    </div>
  );
}
