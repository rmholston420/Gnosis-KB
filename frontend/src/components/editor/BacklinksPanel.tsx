/**
 * BacklinksPanel — shows all notes that link to the current note.
 * Displayed in the editor sidebar / bottom panel.
 */
import React, { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { Link2, ChevronDown, ChevronRight, ExternalLink } from 'lucide-react';
import { useBacklinks } from '../../hooks/useNotes';
import { relativeTime } from '../../lib/dateUtils';
import type { Note } from '../../types';

interface BacklinkRowProps {
  note: Note;
  /** The passage in that note that contains the wikilink. */
  context?: string;
}

function BacklinkRow({ note, context }: BacklinkRowProps) {
  const navigate  = useNavigate();
  const [open, setOpen] = useState(false);

  return (
    <div className="border-b border-gnosis-border last:border-0">
      <button
        onClick={() => context ? setOpen(!open) : navigate(`/notes/${note.note_id}`)}
        className="w-full flex items-center gap-2 px-3 py-2 text-xs hover:bg-gnosis-hover transition-colors group"
      >
        {context ? (
          open ? <ChevronDown size={11} /> : <ChevronRight size={11} />
        ) : (
          <ExternalLink size={11} className="text-gnosis-muted" />
        )}
        <span className="flex-1 text-left font-medium text-gnosis-fg truncate group-hover:text-gnosis-accent">
          {note.title}
        </span>
        <span className="text-gnosis-muted flex-shrink-0">{relativeTime(note.modified_at ?? '')}</span>
      </button>

      {context && open && (
        <div className="px-8 pb-2">
          <p className="text-xs text-gnosis-muted leading-relaxed italic border-l-2 border-gnosis-border pl-2">
            \u2026{context}\u2026
          </p>
          <button
            onClick={() => navigate(`/notes/${note.note_id}`)}
            className="mt-1 text-xs text-gnosis-accent hover:underline flex items-center gap-1"
          >
            <ExternalLink size={10} /> Open note
          </button>
        </div>
      )}
    </div>
  );
}

interface BacklinksPanelProps {
  noteId: string | null;
}

/**
 * Fetches and displays all backlinks for the given note.
 * Shows a count badge and collapses when there are no incoming links.
 */
export function BacklinksPanel({ noteId }: BacklinksPanelProps) {
  const [collapsed, setCollapsed] = useState(false);
  const { data, isLoading } = useBacklinks(noteId);

  const backlinks = data?.backlinks ?? [];
  const count     = data?.count ?? 0;

  return (
    <div className="bg-gnosis-surface border border-gnosis-border rounded-lg overflow-hidden">
      {/* Header */}
      <button
        onClick={() => setCollapsed(!collapsed)}
        className="w-full flex items-center gap-2 px-3 py-2 border-b border-gnosis-border text-xs font-semibold text-gnosis-muted hover:text-gnosis-fg transition-colors"
        aria-expanded={!collapsed}
      >
        <Link2 size={12} />
        <span>Backlinks</span>
        {count > 0 && (
          <span className="ml-1 px-1.5 py-0.5 rounded-full bg-gnosis-accent/15 text-gnosis-accent text-xs">
            {count}
          </span>
        )}
        <span className="ml-auto">
          {collapsed ? <ChevronRight size={12} /> : <ChevronDown size={12} />}
        </span>
      </button>

      {!collapsed && (
        <div>
          {isLoading && (
            <div className="px-3 py-3 space-y-2">
              {[...Array(3)].map((_, i) => (
                <div key={i} className="h-4 rounded bg-gnosis-muted/10 animate-pulse" />
              ))}
            </div>
          )}

          {!isLoading && backlinks.length === 0 && (
            <p className="text-xs text-gnosis-muted px-3 py-3">
              No notes link to this one yet.
            </p>
          )}

          {backlinks.map((bl) => (
            <BacklinkRow
              key={bl.source_note_id ?? bl.note_id}
              note={bl as unknown as Note}
              context={bl.context}
            />
          ))}
        </div>
      )}
    </div>
  );
}
