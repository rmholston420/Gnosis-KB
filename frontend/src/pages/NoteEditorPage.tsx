import { useParams, useNavigate } from 'react-router-dom';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import api from '../services/api';
import NoteEditor from '../components/NoteEditor';
import { useAppStore } from '../store/useAppStore';
import { Loader2, ArrowLeft } from 'lucide-react';
import type { Note, NoteCreate } from '../types';

export default function NoteEditorPage() {
  const { id } = useParams<{ id?: string }>(); // undefined = new note
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const { setActiveNoteId } = useAppStore();

  const { data: note, isLoading } = useQuery<Note>({
    queryKey: ['note', id],
    queryFn: () => api.getNote(id!) as Promise<Note>,
    enabled: !!id,
  });

  const createMutation = useMutation({
    mutationFn: (data: NoteCreate) => api.createNote(data) as Promise<Note>,
    onSuccess: (newNote: Note) => {
      queryClient.invalidateQueries({ queryKey: ['notes'] });
      navigate(`/notes/${newNote.id}`, { replace: true });
      setActiveNoteId(newNote.id);
    },
  });

  const updateMutation = useMutation({
    mutationFn: ({ body, title }: { body: string; title?: string }) =>
      api.updateNote(id!, { body, title }) as Promise<Note>,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['note', id] });
      queryClient.invalidateQueries({ queryKey: ['notes'] });
    },
  });

  if (isLoading) {
    return (
      <div className="flex items-center justify-center h-64">
        <Loader2 className="animate-spin text-text-muted" size={24} />
      </div>
    );
  }

  // New note: show blank editor
  if (!id) {
    const blankNote: Note = {
      id: '',
      title: '',
      slug: '',
      body: '',
      body_html: '',
      note_type: 'permanent',
      status: 'draft',
      folder: '10-zettelkasten',
      word_count: 0,
      is_deleted: false,
      vector_indexed: false,
      graph_indexed: false,
      frontmatter: {},
      tags: [],
      outgoing_links: [],
      incoming_links: [],
    };
    return (
      <div className="h-full flex flex-col">
        <div className="px-4 py-2 border-b border-border flex-shrink-0">
          <button onClick={() => navigate(-1)} className="flex items-center gap-1 text-xs text-text-muted hover:text-text-primary">
            <ArrowLeft size={13} /> Back
          </button>
        </div>
        <div className="flex-1 overflow-hidden">
          <NoteEditor
            note={blankNote}
            onSave={async (body, title) => {
              await createMutation.mutateAsync({
                title: title || 'Untitled',
                body,
                folder: '10-zettelkasten',
              });
            }}
            isLoading={createMutation.isPending}
          />
        </div>
      </div>
    );
  }

  if (!note) return <div className="p-6 text-accent-red">Note not found.</div>;

  return (
    <div className="h-full flex flex-col">
      <div className="px-4 py-2 border-b border-border flex-shrink-0">
        <button onClick={() => navigate('/notes')} className="flex items-center gap-1 text-xs text-text-muted hover:text-text-primary">
          <ArrowLeft size={13} /> All Notes
        </button>
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
