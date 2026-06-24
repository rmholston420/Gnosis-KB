/**
 * DailyNoteWidget — compact sidebar widget that navigates to today's daily note.
 * Shows the date, note title if it exists, and a one-click open/create action.
 */
import React from 'react';
import { useNavigate } from 'react-router-dom';
import { CalendarDays, Plus, Loader2 } from 'lucide-react';
import { useDailyNote } from '../../hooks/useNotes';
import { formatDate, today } from '../../lib/dateUtils';

/**
 * Displayed at the top of the sidebar as a sticky widget.
 * Tapping it opens the daily note, creating it if it doesn't exist.
 */
export function DailyNoteWidget() {
  const navigate = useNavigate();
  const { data: note, isLoading } = useDailyNote();

  const handleOpen = () => {
    if (note) navigate(`/notes/${note.note_id}`);
    else      navigate('/daily');
  };

  return (
    <button
      onClick={handleOpen}
      className="w-full flex items-center gap-2 px-3 py-2 text-xs hover:bg-gnosis-hover transition-colors border-b border-gnosis-border"
      aria-label="Open today's daily note"
    >
      <CalendarDays size={13} className="text-gnosis-accent flex-shrink-0" />
      <div className="flex-1 text-left min-w-0">
        <p className="font-medium text-gnosis-fg truncate">
          {isLoading ? 'Loading\u2026' : (note?.title ?? 'Daily Note')}
        </p>
        <p className="text-gnosis-muted">{formatDate(`${today()}T00:00:00Z`)}</p>
      </div>
      {isLoading ? (
        <Loader2 size={12} className="animate-spin text-gnosis-muted" />
      ) : !note ? (
        <Plus size={12} className="text-gnosis-muted" />
      ) : null}
    </button>
  );
}
