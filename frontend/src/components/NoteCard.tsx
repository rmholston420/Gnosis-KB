/**
 * NoteCard — compact note list item / search result card.
 */
import React from 'react';
import { Link } from 'react-router-dom';
import type { Note } from '../types';
import { relativeTime } from '../lib/dateUtils';
import { TagBadge } from './shared/TagBadge';

const NOTE_TYPE_COLORS: Record<string, string> = {
  permanent:  'bg-blue-500/15 text-blue-700 dark:text-blue-300',
  fleeting:   'bg-slate-400/15 text-slate-600 dark:text-slate-300',
  project:    'bg-amber-500/15 text-amber-700 dark:text-amber-300',
  area:       'bg-emerald-500/15 text-emerald-700 dark:text-emerald-300',
  resource:   'bg-purple-500/15 text-purple-700 dark:text-purple-300',
  journal:    'bg-pink-500/15 text-pink-700 dark:text-pink-300',
  moc:        'bg-red-500/15 text-red-700 dark:text-red-300',
  literature: 'bg-orange-500/15 text-orange-700 dark:text-orange-300',
  default:    'bg-gnosis-border/30 text-gnosis-muted',
};

interface Props {
  note:      Note;
  compact?:  boolean;
  onClick?:  (note: Note) => void;
  selected?: boolean;
}

export function NoteCard({ note, compact = false, onClick, selected = false }: Props) {
  const typeClass =
    NOTE_TYPE_COLORS[note.note_type ?? 'default'] ?? NOTE_TYPE_COLORS['default'];

  const inner = (
    <div
      className={[
        'rounded-lg border transition-colors cursor-pointer',
        'bg-gnosis-surface border-gnosis-border',
        'hover:bg-gnosis-hover',
        selected ? 'ring-2 ring-gnosis-accent' : '',
        compact ? 'p-3' : 'p-4',
      ].join(' ')}
      onClick={() => onClick?.(note)}
      role="button"
      tabIndex={0}
      onKeyDown={(e) => e.key === 'Enter' && onClick?.(note)}
    >
      {/* Header row */}
      <div className="flex items-start justify-between gap-2 mb-1">
        <h3 className={['font-medium text-gnosis-fg line-clamp-1', compact ? 'text-sm' : 'text-base'].join(' ')}>
          {note.title}
        </h3>
        {note.note_type && (
          <span className={`shrink-0 text-xs px-1.5 py-0.5 rounded-full font-medium ${typeClass}`}>
            {note.note_type}
          </span>
        )}
      </div>

      {/* Body excerpt */}
      {!compact && note.body && (
        <p className="text-sm text-gnosis-muted line-clamp-2 mb-2">
          {note.body.replace(/^---[\s\S]*?---\n?/, '').trim().slice(0, 200)}
        </p>
      )}

      {/* Tags + timestamp */}
      <div className="flex items-center gap-2 flex-wrap mt-1">
        {note.tags?.slice(0, 3).map((t) => (
          <TagBadge key={t} tag={t} />
        ))}
        {note.updated_at && (
          <span className="ml-auto text-xs text-gnosis-muted shrink-0">
            {relativeTime(note.updated_at)}
          </span>
        )}
      </div>
    </div>
  );

  // Wrap in a Link when no onClick is provided
  if (!onClick) {
    return <Link to={`/notes/${note.note_id}`}>{inner}</Link>;
  }
  return inner;
}

export default NoteCard;
