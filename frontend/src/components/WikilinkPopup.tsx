/**
 * WikilinkPopup
 * =============
 * Floating card that appears when the user hovers a resolved [[wikilink]].
 *
 * Shows:
 *   - Note title
 *   - Folder badge
 *   - First ~200 chars of plain-text body
 *   - Word count
 *   - "Open note" action
 *
 * Usage:
 *   Managed entirely by WikilinkPreview via mouseenter/mouseleave on
 *   .wikilink-exists elements. This component is portal-rendered so it
 *   escapes any overflow:hidden parents.
 */

import { useEffect, useRef, useState } from 'react';
import { createPortal } from 'react-dom';
import { useNavigate } from 'react-router-dom';
import { ArrowUpRight, FileText } from 'lucide-react';
import type { NoteListItem } from '../types';

interface PopupState {
  note: NoteListItem;
  anchorRect: DOMRect;
}

interface WikilinkPopupProps {
  state: PopupState | null;
  onClose: () => void;
}

// Strip markdown syntax for the snippet
function stripMarkdown(md: string): string {
  return md
    .replace(/```[\s\S]*?```/g, '')
    .replace(/`[^`]+`/g, '')
    .replace(/!?\[[^\]]*\]\([^)]*\)/g, '')
    .replace(/\[\[[^\]]+\]\]/g, '')
    .replace(/[#*_~>]/g, '')
    .replace(/\s+/g, ' ')
    .trim();
}

export default function WikilinkPopup({ state, onClose }: WikilinkPopupProps) {
  const navigate = useNavigate();
  const popupRef = useRef<HTMLDivElement>(null);
  const [position, setPosition] = useState({ top: 0, left: 0 });
  const [visible, setVisible] = useState(false);

  useEffect(() => {
    if (!state) {
      setVisible(false);
      return;
    }

    const { anchorRect } = state;
    const POPUP_W = 300;
    const POPUP_H = 160; // approximate
    const GAP = 8;
    const vw = window.innerWidth;
    const vh = window.innerHeight;

    let top = anchorRect.bottom + GAP + window.scrollY;
    let left = anchorRect.left + window.scrollX;

    // Flip above if it would overflow the bottom
    if (anchorRect.bottom + POPUP_H + GAP > vh) {
      top = anchorRect.top - POPUP_H - GAP + window.scrollY;
    }
    // Clamp left so it doesn't overflow right edge
    if (left + POPUP_W > vw) {
      left = vw - POPUP_W - 8;
    }

    setPosition({ top, left });
    // Tiny delay so the first render doesn't flash at 0,0
    requestAnimationFrame(() => setVisible(true));
  }, [state]);

  if (!state) return null;

  const { note } = state;

  function handleOpen(e: React.MouseEvent) {
    e.preventDefault();
    e.stopPropagation();
    onClose();
    navigate(`/notes/${note.id}`);
  }

  return createPortal(
    <div
      ref={popupRef}
      role="tooltip"
      className="wikilink-popup"
      style={{
        position: 'absolute',
        top: position.top,
        left: position.left,
        width: 300,
        zIndex: 9999,
        opacity: visible ? 1 : 0,
        transform: visible ? 'translateY(0)' : 'translateY(-4px)',
        transition: 'opacity 120ms ease, transform 120ms ease',
        pointerEvents: visible ? 'auto' : 'none',
      }}
      // Keep popup open when mouse moves into it
      onMouseEnter={() => setVisible(true)}
      onMouseLeave={onClose}
    >
      <div className="wikilink-popup-inner">
        {/* Header */}
        <div className="wikilink-popup-header">
          <FileText size={12} className="wikilink-popup-icon" />
          <span className="wikilink-popup-title">{note.title}</span>
          <button
            className="wikilink-popup-open"
            onClick={handleOpen}
            title="Open note"
            aria-label={`Open note: ${note.title}`}
          >
            <ArrowUpRight size={13} />
          </button>
        </div>

        {/* Folder badge */}
        <div className="wikilink-popup-meta">
          <span className="wikilink-popup-folder">{note.folder}</span>
          <span className="wikilink-popup-words">{note.word_count}w</span>
        </div>

        {/* Tags */}
        {note.tags.length > 0 && (
          <div className="wikilink-popup-tags">
            {note.tags.slice(0, 4).map((t) => (
              <span key={t} className="wikilink-popup-tag">{t}</span>
            ))}
          </div>
        )}
      </div>
    </div>,
    document.body,
  );
}

export type { PopupState };
