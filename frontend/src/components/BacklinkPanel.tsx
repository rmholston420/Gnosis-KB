/**
 * BacklinkPanel
 * =============
 * Shows all notes that link TO the currently open note ([[backlinks]])
 * and all notes the current note links OUT TO.
 *
 * Appears as a collapsible sidebar panel below the editor.
 * Clicking any entry navigates to that note.
 */

import { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { Link2, ArrowRight, ArrowLeft, ChevronDown, ChevronRight } from 'lucide-react';
import type { LinkRef } from '../types';

interface BacklinkPanelProps {
  noteId: string;
  incomingLinks: LinkRef[];
  outgoingLinks: LinkRef[];
  /** Map of note id → title for display */
  noteTitlesById: Map<string, string>;
}

interface LinkRowProps {
  noteId: string;
  title: string;
  context?: string;
  direction: 'in' | 'out';
  onClick: () => void;
}

function LinkRow({ title, context, direction, onClick }: LinkRowProps) {
  return (
    <button
      onClick={onClick}
      className="w-full text-left px-3 py-2 rounded hover:bg-bg-elevated group flex items-start gap-2 transition-colors"
    >
      <span className="mt-0.5 flex-shrink-0 text-text-faint">
        {direction === 'in' ? <ArrowRight size={13} /> : <ArrowLeft size={13} />}
      </span>
      <div className="flex-1 min-w-0">
        <div className="text-sm text-text-primary group-hover:text-teal-400 truncate transition-colors">
          {title}
        </div>
        {context && (
          <div className="text-xs text-text-faint mt-0.5 line-clamp-1 italic">
            &ldquo;{context}&rdquo;
          </div>
        )}
      </div>
    </button>
  );
}

function Section({
  label,
  count,
  children,
  defaultOpen = true,
}: {
  label: string;
  count: number;
  children: React.ReactNode;
  defaultOpen?: boolean;
}) {
  const [open, setOpen] = useState(defaultOpen);
  return (
    <div className="mb-3">
      <button
        onClick={() => setOpen((v) => !v)}
        className="w-full flex items-center gap-1.5 px-3 py-1.5 text-xs font-medium text-text-muted hover:text-text-primary transition-colors"
      >
        {open ? <ChevronDown size={12} /> : <ChevronRight size={12} />}
        {label}
        <span className="ml-auto tabular-nums text-text-faint">{count}</span>
      </button>
      {open && <div className="mt-0.5">{children}</div>}
    </div>
  );
}

export default function BacklinkPanel({
  noteId,
  incomingLinks,
  outgoingLinks,
  noteTitlesById,
}: BacklinkPanelProps) {
  const navigate = useNavigate();
  const [panelOpen, setPanelOpen] = useState(true);

  const totalLinks = incomingLinks.length + outgoingLinks.length;

  if (totalLinks === 0) {
    return (
      <div className="border-t border-border px-4 py-3">
        <div className="flex items-center gap-1.5 text-xs text-text-faint">
          <Link2 size={12} />
          <span>No links</span>
        </div>
      </div>
    );
  }

  return (
    <div className="border-t border-border">
      {/* Panel toggle header */}
      <button
        onClick={() => setPanelOpen((v) => !v)}
        className="w-full flex items-center gap-1.5 px-4 py-2.5 text-xs font-medium text-text-muted hover:text-text-primary transition-colors"
      >
        <Link2 size={12} />
        <span>Links</span>
        <span className="ml-1 tabular-nums text-text-faint">{totalLinks}</span>
        <span className="ml-auto">
          {panelOpen ? <ChevronDown size={12} /> : <ChevronRight size={12} />}
        </span>
      </button>

      {panelOpen && (
        <div className="pb-2">
          {incomingLinks.length > 0 && (
            <Section label="Linked here" count={incomingLinks.length}>
              {incomingLinks.map((link) => (
                <LinkRow
                  key={`${link.source_id}-${link.target_id}`}
                  noteId={link.source_id}
                  title={noteTitlesById.get(link.source_id) ?? link.source_id}
                  context={link.context}
                  direction="in"
                  onClick={() => navigate(`/notes/${link.source_id}`)}
                />
              ))}
            </Section>
          )}

          {outgoingLinks.length > 0 && (
            <Section label="Links out" count={outgoingLinks.length} defaultOpen={true}>
              {outgoingLinks.map((link) => (
                <LinkRow
                  key={`${link.source_id}-${link.target_id}`}
                  noteId={link.target_id}
                  title={noteTitlesById.get(link.target_id) ?? link.target_id}
                  context={link.context}
                  direction="out"
                  onClick={() => navigate(`/notes/${link.target_id}`)}
                />
              ))}
            </Section>
          )}
        </div>
      )}
    </div>
  );
}
