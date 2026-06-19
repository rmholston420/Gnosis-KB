import { useNavigate } from 'react-router-dom';
import { formatDistanceToNow } from 'date-fns';
import type { NoteListItem, NoteType } from '../types';

const NOTE_TYPE_COLORS: Record<NoteType, string> = {
  permanent: 'text-note-permanent bg-note-permanent/10',
  fleeting: 'text-note-fleeting bg-note-fleeting/10',
  literature: 'text-note-literature bg-note-literature/10',
  journal: 'text-note-journal bg-note-journal/10',
  map: 'text-note-map bg-note-map/10',
  reference: 'text-note-reference bg-note-reference/10',
  project: 'text-note-project bg-note-project/10',
  template: 'text-text-secondary bg-bg-tertiary',
};

interface NoteCardProps {
  note: NoteListItem;
  active?: boolean;
}

export default function NoteCard({ note, active }: NoteCardProps) {
  const navigate = useNavigate();

  return (
    <button
      onClick={() => navigate(`/notes/${note.id}`)}
      className={`w-full text-left p-3 rounded border transition-all hover:border-border-muted ${
        active
          ? 'border-accent-blue bg-bg-elevated'
          : 'border-border-subtle bg-bg-secondary hover:bg-bg-tertiary'
      }`}
    >
      <div className="flex items-start justify-between gap-2 mb-1.5">
        <h3 className="text-sm font-medium text-text-primary leading-snug line-clamp-2 flex-1">
          {note.title}
        </h3>
        <span
          className={`text-xs px-1.5 py-0.5 rounded flex-shrink-0 capitalize ${
            NOTE_TYPE_COLORS[note.note_type] || 'text-text-secondary bg-bg-tertiary'
          }`}
        >
          {note.note_type}
        </span>
      </div>
      <div className="flex items-center gap-2 text-xs text-text-muted">
        <span>{note.word_count}w</span>
        <span>·</span>
        {note.modified_at ? (
          <span>{formatDistanceToNow(new Date(note.modified_at), { addSuffix: true })}</span>
        ) : note.created_at ? (
          <span>{formatDistanceToNow(new Date(note.created_at), { addSuffix: true })}</span>
        ) : null}
        {note.tags.length > 0 && (
          <>
            <span>·</span>
            <span className="truncate">{note.tags.slice(0, 2).map(t => `#${t}`).join(' ')}</span>
          </>
        )}
      </div>
    </button>
  );
}
