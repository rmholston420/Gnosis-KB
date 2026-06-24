/**
 * NoteCard — reusable card for Note objects.
 * Used by NotesPage (grid) and SearchPage (list via onResultClick).
 */
import React from 'react';
import { useNavigate } from 'react-router-dom';
import { Calendar, Tag } from 'lucide-react';
import { TagBadge } from '../shared/TagBadge';
import type { Note } from '../../types';

interface NoteCardProps {
  note: Note;
  onClick?: (noteId: string) => void;
  compact?: boolean;
}

const TYPE_COLOR: Record<string, string> = {
  permanent:  'text-gnosis-accent',
  literature: 'text-blue-400',
  fleeting:   'text-gnosis-muted',
  index:      'text-yellow-400',
  structure:  'text-purple-400',
};

export function NoteCard({ note, onClick, compact = false }: NoteCardProps) {
  const navigate = useNavigate();
  const handleClick = () => (onClick ? onClick(note.note_id) : navigate(`/notes/${note.note_id}`));
  const handleKey   = (e: React.KeyboardEvent) => { if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); handleClick(); } };
  const tc = TYPE_COLOR[note.note_type ?? 'permanent'] ?? 'text-gnosis-muted';

  if (compact) {
    return (
      <button type="button" onClick={handleClick} onKeyDown={handleKey}
        className="w-full text-left flex items-start gap-3 px-3 py-2.5 rounded-lg hover:bg-gnosis-hover transition-colors group">
        <div className="min-w-0 flex-1">
          <p className="text-sm font-medium text-gnosis-fg truncate group-hover:text-gnosis-accent transition-colors">{note.title}</p>
          {note.body && <p className="text-xs text-gnosis-muted line-clamp-1 mt-0.5">{note.body.slice(0, 120)}</p>}
        </div>
      </button>
    );
  }

  return (
    <article onClick={handleClick} onKeyDown={handleKey} role="button" tabIndex={0}
      aria-label={`Open note: ${note.title}`}
      className="bg-gnosis-surface border border-gnosis-border rounded-xl p-4 cursor-pointer hover:border-gnosis-accent/40 hover:shadow-md transition-all group">
      <div className="flex items-start justify-between gap-2 mb-2">
        <h3 className="text-sm font-semibold text-gnosis-fg group-hover:text-gnosis-accent transition-colors line-clamp-2">{note.title}</h3>
        {note.note_type && <span className={`text-xs font-medium flex-shrink-0 ${tc}`}>{note.note_type}</span>}
      </div>
      {note.body && <p className="text-xs text-gnosis-muted line-clamp-3 mb-3 leading-relaxed">{note.body.slice(0, 200)}</p>}
      <div className="flex items-center justify-between gap-2">
        <div className="flex flex-wrap gap-1 min-w-0">
          {(note.tags ?? []).slice(0, 4).map((t) => <TagBadge key={t} tag={t} />)}
          {(note.tags ?? []).length > 4 && (
            <span className="text-xs text-gnosis-muted flex items-center gap-0.5"><Tag size={10} /> +{(note.tags?.length ?? 0) - 4}</span>
          )}
        </div>
        {note.created_at && (
          <span className="text-xs text-gnosis-muted flex items-center gap-1 flex-shrink-0">
            <Calendar size={10} />
            {new Date(note.created_at).toLocaleDateString(undefined, { month: 'short', day: 'numeric' })}
          </span>
        )}
      </div>
    </article>
  );
}
