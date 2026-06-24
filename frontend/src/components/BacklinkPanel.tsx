/**
 * BacklinkPanel
 * =============
 * Shows all notes that link TO the current note (incoming)
 * and all notes the current note links TO (outgoing).
 *
 * Used in the right-side drawer on note detail / editor pages.
 *
 * Props:
 *   noteId        — the currently viewed note id
 *   incomingLinks — LinkRef[] of notes that reference this one
 *   outgoingLinks — LinkRef[] of notes this one references
 *   noteTitlesById — id → title lookup (Map or Record) for rendering
 */

import { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { ArrowLeft, ArrowRight, Link2, ChevronDown, ChevronRight } from 'lucide-react';
import type { LinkRef } from '../types';

interface BacklinkPanelProps {
  noteId: string;
  incomingLinks: LinkRef[];
  outgoingLinks: LinkRef[];
  noteTitlesById?: Map<string, string> | Record<string, string>;
}

function lookupTitle(
  id: string,
  map?: Map<string, string> | Record<string, string>,
): string {
  if (!map) return id;
  if (map instanceof Map) return map.get(id) ?? id;
  return (map as Record<string, string>)[id] ?? id;
}

export default function BacklinkPanel({
  noteId: _noteId,
  incomingLinks,
  outgoingLinks,
  noteTitlesById,
}: BacklinkPanelProps) {
  const navigate = useNavigate();
  const totalLinks = incomingLinks.length + outgoingLinks.length;
  const [panelOpen, setPanelOpen] = useState(true);
  const [incomingOpen, setIncomingOpen] = useState(true);
  const [outgoingOpen, setOutgoingOpen] = useState(false);

  // No links at all — static placeholder, no toggle
  if (totalLinks === 0) {
    return (
      <div className="px-3 py-3">
        <p className="text-xs text-text-faint">No links</p>
      </div>
    );
  }

  function LinkChip({ linkRef, navigateId }: { linkRef: LinkRef; navigateId: string }) {
    const title = lookupTitle(navigateId, noteTitlesById);
    return (
      <button
        onClick={() => navigate(`/notes/${navigateId}`)}
        className="flex items-center gap-1.5 rounded-md bg-bg-elevated px-2.5 py-1.5 text-xs text-text-muted hover:bg-bg-tertiary hover:text-text-primary transition-colors w-full text-left"
        title={title}
      >
        <Link2 size={10} className="flex-shrink-0 text-text-faint" />
        <span className="truncate">
          {title}
          {linkRef.link_text && linkRef.link_text !== title && (
            <span className="ml-1 text-text-faint">({linkRef.link_text})</span>
          )}
        </span>
      </button>
    );
  }

  return (
    <div className="flex flex-col">
      {/* Top-level toggle */}
      <button
        onClick={() => setPanelOpen((v) => !v)}
        className="flex items-center gap-1.5 px-3 py-2 text-xs font-medium text-text-muted hover:text-text-primary transition-colors w-full text-left"
      >
        {panelOpen ? <ChevronDown size={12} /> : <ChevronRight size={12} />}
        Links {totalLinks}
      </button>

      {panelOpen && (
        <div className="flex flex-col gap-3 px-3 pb-3">
          {/* Incoming */}
          <section>
            <button
              onClick={() => setIncomingOpen((v) => !v)}
              className="mb-1.5 flex items-center gap-1.5 w-full"
            >
              <ArrowLeft size={12} className="text-text-faint" />
              <span className="text-xs font-medium text-text-muted uppercase tracking-wide">
                Linked here ({incomingLinks.length})
              </span>
              {incomingOpen ? <ChevronDown size={10} className="ml-auto text-text-faint" /> : <ChevronRight size={10} className="ml-auto text-text-faint" />}
            </button>
            {incomingOpen && (
              incomingLinks.length === 0
                ? <p className="text-xs text-text-faint pl-1">No notes link here yet.</p>
                : <div className="flex flex-col gap-1">
                    {incomingLinks.map((lk) => (
                      <LinkChip key={`${lk.source_id}-${lk.target_id}`} linkRef={lk} navigateId={lk.source_id ?? ''} />
                    ))}
                  </div>
            )}
          </section>

          {/* Outgoing */}
          <section>
            <button
              onClick={() => setOutgoingOpen((v) => !v)}
              className="mb-1.5 flex items-center gap-1.5 w-full"
            >
              <ArrowRight size={12} className="text-text-faint" />
              <span className="text-xs font-medium text-text-muted uppercase tracking-wide">
                Links out ({outgoingLinks.length})
              </span>
              {outgoingOpen ? <ChevronDown size={10} className="ml-auto text-text-faint" /> : <ChevronRight size={10} className="ml-auto text-text-faint" />}
            </button>
            {outgoingOpen && (
              outgoingLinks.length === 0
                ? <p className="text-xs text-text-faint pl-1">This note has no outgoing links.</p>
                : <div className="flex flex-col gap-1">
                    {outgoingLinks.map((lk) => (
                      <LinkChip key={`${lk.source_id}-${lk.target_id}`} linkRef={lk} navigateId={lk.target_id ?? ''} />
                    ))}
                  </div>
            )}
          </section>
        </div>
      )}
    </div>
  );
}
