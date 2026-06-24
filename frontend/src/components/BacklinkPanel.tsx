/**
 * BacklinkPanel
 * =============
 * Shows all notes that link TO the current note (incoming)
 * and all notes the current note links TO (outgoing).
 *
 * Used in the right-side drawer on note detail / editor pages.
 *
 * Props:
 *   noteId        — the currently viewed note id (used by parent; kept for API
 *                    symmetry)
 *   incomingLinks — list of notes that reference this one
 *   outgoingLinks — list of notes this one references
 *   noteTitlesById — id → title lookup for rendering link chips
 */

import { useNavigate } from 'react-router-dom';
import { ArrowLeft, ArrowRight, Link2 } from 'lucide-react';
import type { NoteListItem } from '../types';

interface BacklinkPanelProps {
  noteId: string;
  incomingLinks: NoteListItem[];
  outgoingLinks: NoteListItem[];
  noteTitlesById?: Record<string, string>;
}

export default function BacklinkPanel({
  noteId: _noteId,
  incomingLinks,
  outgoingLinks,
  noteTitlesById,
}: BacklinkPanelProps) {
  const navigate = useNavigate();

  function NoteChip({ note }: { note: NoteListItem }) {
    return (
      <button
        onClick={() => navigate(`/notes/${note.id}`)}
        className="flex items-center gap-1.5 rounded-md bg-bg-elevated px-2.5 py-1.5 text-xs text-text-muted hover:bg-bg-tertiary hover:text-text-primary transition-colors w-full text-left"
        title={note.title}
      >
        <Link2 size={10} className="flex-shrink-0 text-text-faint" />
        <span className="truncate">{noteTitlesById?.[note.id] ?? note.title}</span>
      </button>
    );
  }

  return (
    <div className="flex flex-col gap-4 p-3">
      {/* Incoming links */}
      <section>
        <div className="mb-2 flex items-center gap-1.5">
          <ArrowLeft size={12} className="text-text-faint" />
          <span className="text-xs font-medium text-text-muted uppercase tracking-wide">
            Linked here ({incomingLinks.length})
          </span>
        </div>
        {incomingLinks.length === 0 ? (
          <p className="text-xs text-text-faint pl-1">No notes link here yet.</p>
        ) : (
          <div className="flex flex-col gap-1">
            {incomingLinks.map((n) => <NoteChip key={n.id} note={n} />)}
          </div>
        )}
      </section>

      {/* Outgoing links */}
      <section>
        <div className="mb-2 flex items-center gap-1.5">
          <ArrowRight size={12} className="text-text-faint" />
          <span className="text-xs font-medium text-text-muted uppercase tracking-wide">
            Links to ({outgoingLinks.length})
          </span>
        </div>
        {outgoingLinks.length === 0 ? (
          <p className="text-xs text-text-faint pl-1">This note has no outgoing links.</p>
        ) : (
          <div className="flex flex-col gap-1">
            {outgoingLinks.map((n) => <NoteChip key={n.id} note={n} />)}
          </div>
        )}
      </section>
    </div>
  );
}
