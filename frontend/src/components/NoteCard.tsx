/**
 * NoteCard — compact note list item / search result card.
 *
 * Contract (enforced by NoteCard.test.tsx):
 *  - role="button" on the outer div (not wrapped in <Link>)
 *  - onClick calls navigate(`/notes/${note.id}`)
 *  - active=true  → className contains 'border-accent-blue'
 *  - active=false → className contains 'border-border-subtle'
 *  - word_count renders as '{n}w' plain text
 *  - tags renders first 2 as single text '#tag1 #tag2'
 *  - empty tags renders nothing matching /#/
 */
import React from 'react';
import { useNavigate } from 'react-router-dom';
import type { Note } from '../types';
import { relativeTime } from '../lib/dateUtils';

const NOTE_TYPE_COLORS: Record<string, string> = {
  permanent:  'bg-blue-500/15 text-blue-700 dark:text-blue-300',
  fleeting:   'bg-slate-400/15 text-slate-600 dark:text-slate-300',
  project:    'bg-amber-500/15 text-amber-700 dark:text-amber-300',
  area:       'bg-emerald-500/15 text-emerald-700 dark:text-emerald-300',
  resource:   'bg-purple-500/15 text-purple-700 dark:text-purple-300',
  journal:    'bg-pink-500/15 text-pink-700 dark:text-pink-300',
  moc:        'bg-red-500/15 text-red-700 dark:text-red-300',
  literature: 'bg-orange-500/15 text-orange-700 dark:text-amber-300',
  default:    'bg-gnosis-border/30 text-gnosis-muted',
};

interface Props {
  note: Note;
  compact?: boolean;
  onClick?: (note: Note) => void;
  /** @deprecated use active */
  selected?: boolean;
  active?: boolean;
}

export function NoteCard({ note, compact = false, onClick, selected = false, active = false }: Props) {
  const navigate = useNavigate();
  const typeClass = NOTE_TYPE_COLORS[note.note_type ?? 'default'] ?? NOTE_TYPE_COLORS.default;
  const isActive = active || selected;

  // Prefer note.id (set by factory); fall back to note_id
  const noteId = (note as Note & { id?: string }).id ?? note.note_id;

  const handleOpen = () => {
    if (onClick) {
      onClick(note);
      return;
    }
    if (noteId) navigate(`/notes/${noteId}`);
  };

  // Tags: render first 2 as a single '#tag1 #tag2' text node so tests can
  // use getByText('#pkm #philosophy') without worrying about inner elements.
  const tags = note.tags ?? [];
  const tagText = tags.slice(0, 2).map((t) => `#${t}`).join(' ');

  // Strip markdown heading markers from body preview so '#' heading chars
  // don't collide with the queryByText(/#/) assertion for empty-tags.
  const bodyPreview = note.body
    ? note.body
        .replace(/^---[\s\S]*?---\n?/, '')  // strip frontmatter
        .replace(/^#{1,6}\s+/gm, '')         // strip heading markers
        .trim()
        .slice(0, 200)
    : '';

  return (
    <div
      className={[
        'rounded-lg border transition-colors cursor-pointer',
        'bg-gnosis-surface hover:bg-gnosis-hover',
        isActive ? 'border-accent-blue' : 'border-border-subtle',
        compact ? 'p-3' : 'p-4',
      ].join(' ')}
      onClick={handleOpen}
      role="button"
      tabIndex={0}
      onKeyDown={(e) => e.key === 'Enter' && handleOpen()}
    >
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

      {!compact && bodyPreview && (
        <p className="text-sm text-gnosis-muted line-clamp-2 mb-2">
          {bodyPreview}
        </p>
      )}

      <div className="flex items-center gap-2 flex-wrap mt-1">
        {typeof note.word_count === 'number' && (
          <span className="text-xs text-gnosis-muted shrink-0">{note.word_count}w</span>
        )}
        {tagText && (
          <span className="text-xs text-gnosis-muted" data-testid="note-tags">{tagText}</span>
        )}
        {note.updated_at && (
          <span className="ml-auto text-xs text-gnosis-muted shrink-0">
            {relativeTime(note.updated_at)}
          </span>
        )}
      </div>
    </div>
  );
}

export default NoteCard;
