/**
 * WikilinkPopup
 * =============
 * Floating card that appears when hovering a resolved [[wikilink]]
 * inside WikilinkPreview or the note editor.
 *
 * Usage:
 *   <WikilinkPopup state={popup} onClose={scheduleHide} />
 *
 * The parent is responsible for computing `state` (bounding rect + note)
 * and calling `onClose` when the mouse leaves both the anchor and this popup.
 */

import { useNavigate } from 'react-router-dom';
import { ExternalLink, FileText } from 'lucide-react';
import type { NoteListItem } from '../types';

// NoteListItem doesn't carry body/body_html, but a popup context may pass
// a richer object. We extend locally so the popup works with either shape.
type PopupNote = NoteListItem & { body?: string };

export interface PopupState {
  note: PopupNote;
  anchorRect: DOMRect;
}

interface WikilinkPopupProps {
  state: PopupState | null;
  onClose: () => void;
}

export default function WikilinkPopup({ state, onClose }: WikilinkPopupProps) {
  const navigate = useNavigate();

  if (!state) return null;

  const { note, anchorRect } = state;

  // Position: prefer below the anchor; fall back to above if near bottom
  const spaceBelow = window.innerHeight - anchorRect.bottom;
  const popupHeight = 140;
  const top = spaceBelow > popupHeight + 8
    ? anchorRect.bottom + window.scrollY + 6
    : anchorRect.top    + window.scrollY - popupHeight - 6;

  const left = Math.min(
    anchorRect.left + window.scrollX,
    window.innerWidth - 300 - 8,
  );

  const snippet = note.body
    ? note.body.slice(0, 160).replace(/\n/g, ' ') + (note.body.length > 160 ? '\u2026' : '')
    : 'No preview available.';

  return (
    <div
      className="wikilink-popup"
      style={{
        position: 'absolute',
        top,
        left,
        width: 300,
        zIndex: 9000,
        pointerEvents: 'auto',
      }}
      onMouseEnter={() => { /* cancel hide — parent manages timer */ }}
      onMouseLeave={onClose}
    >
      <div className="rounded-lg border border-border-default bg-bg-elevated shadow-lg p-3">
        <div className="flex items-start justify-between gap-2 mb-1.5">
          <div className="flex items-center gap-1.5 min-w-0">
            <FileText size={12} className="text-text-faint flex-shrink-0" />
            <span className="text-xs font-semibold text-text-primary truncate">{note.title}</span>
          </div>
          <button
            onClick={() => navigate(`/notes/${note.id}`)}
            className="flex-shrink-0 text-text-faint hover:text-accent-blue transition-colors"
            title="Open note"
          >
            <ExternalLink size={11} />
          </button>
        </div>
        {note.tags.length > 0 && (
          <div className="flex flex-wrap gap-1 mb-1.5">
            {note.tags.slice(0, 3).map((t) => (
              <span key={t} className="rounded-full bg-bg-tertiary px-1.5 py-0.5 text-xs text-text-faint">#{t}</span>
            ))}
          </div>
        )}
        <p className="text-xs text-text-muted leading-relaxed line-clamp-3">{snippet}</p>
      </div>
    </div>
  );
}
