/**
 * NoteListItem
 * ============
 * Single note row rendered inside NoteFolderGroup or flat note lists.
 * Shows title, note_type badge, and word count. Clicking navigates to /notes/:id.
 */
import React from 'react';
import { Link } from 'react-router-dom';
import { FileText, Lightbulb, Bookmark, Star } from 'lucide-react';
import { TagBadge } from '../shared/TagBadge';
import type { Note } from '../../types';

const TYPE_ICON: Record<string, React.ReactNode> = {
  permanent:   <Star      size={11} />,
  literature:  <Bookmark  size={11} />,
  fleeting:    <Lightbulb size={11} />,
  moc:         <FileText  size={11} />,
};

interface Props {
  note: Note;
  selected?: boolean;
  onSelect?: (note: Note) => void;
}

export function NoteListItem({ note, selected, onSelect }: Props) {
  return (
    <Link
      to={`/notes/${note.note_id}`}
      onClick={() => onSelect?.(note)}
      className={[
        'flex items-start gap-2 px-3 py-1.5 rounded text-sm transition-colors group',
        selected
          ? 'bg-gnosis-surface text-gnosis-fg'
          : 'text-gnosis-muted hover:bg-gnosis-hover hover:text-gnosis-fg',
      ].join(' ')}
      aria-current={selected ? 'page' : undefined}
    >
      {/* Type icon */}
      <span className="mt-0.5 shrink-0 text-gnosis-muted/60 group-hover:text-gnosis-muted">
        {TYPE_ICON[note.note_type ?? ''] ?? <FileText size={11} />}
      </span>

      {/* Title + meta */}
      <div className="flex-1 min-w-0">
        <p className="truncate font-medium leading-snug">{note.title || 'Untitled'}</p>
        {note.tags && note.tags.length > 0 && (
          <div className="flex flex-wrap gap-0.5 mt-0.5">
            {note.tags.slice(0, 3).map((tag) => (
              <TagBadge key={tag} tag={tag} size="xs" />
            ))}
          </div>
        )}
      </div>

      {/* Word count */}
      <span className="shrink-0 text-xs tabular-nums text-gnosis-muted/50 mt-0.5">
        {note.word_count ?? 0}w
      </span>
    </Link>
  );
}
