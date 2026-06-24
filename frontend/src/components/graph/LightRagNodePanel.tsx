/**
 * LightRagNodePanel
 * =================
 * Pure prop-driven slide-in panel showing a LightRAG graph entity's
 * details, incident relations, and linked source notes.
 *
 * Props
 * -----
 *   entity           — entity to display (null → renders nothing)
 *   relations        — ALL graph relations; component filters to incident ones
 *   notes            — flat list of NoteListItem for source-note lookup
 *   onClose          — called when user dismisses the panel
 *   onNavigateToNote — called with noteId when user clicks a source note link
 */
import React, { useEffect, useRef } from 'react';
import { X } from 'lucide-react';

// ---------------------------------------------------------------------------
// Public types (exported so tests can import them)
// ---------------------------------------------------------------------------
export interface LightRagEntity {
  id: string;
  label: string;
  description?: string;
  source_note_ids?: string[];
}

export interface LightRagRelation {
  source: string;
  target: string;
  label: string;
  weight?: number;
}

export interface NoteListItem {
  id: string;
  title: string;
  folder?: string | null;
}

// ---------------------------------------------------------------------------
// Props
// ---------------------------------------------------------------------------
interface Props {
  entity: LightRagEntity | null;
  relations: LightRagRelation[];
  notes: NoteListItem[];
  onClose: () => void;
  onNavigateToNote: (noteId: string) => void;
}

// ---------------------------------------------------------------------------
// Component
// ---------------------------------------------------------------------------
export default function LightRagNodePanel({
  entity,
  relations,
  notes,
  onClose,
  onNavigateToNote,
}: Props) {
  const panelRef = useRef<HTMLElement | null>(null);

  // Close on Escape
  useEffect(() => {
    function handleKey(e: KeyboardEvent) {
      if (e.key === 'Escape') onClose();
    }
    window.addEventListener('keydown', handleKey);
    return () => window.removeEventListener('keydown', handleKey);
  }, [onClose]);

  // Focus panel for a11y
  useEffect(() => {
    if (entity && panelRef.current) panelRef.current.focus();
  }, [entity]);

  if (!entity) return null;

  // Filter to incident relations (entity is source OR target)
  const incidentRelations = relations.filter(
    (r) => r.source === entity.id || r.target === entity.id
  );

  // Resolve source notes
  const sourceNoteIds = entity.source_note_ids ?? [];
  const noteMap = new Map(notes.map((n) => [n.id, n]));
  const sourceNotes = sourceNoteIds
    .map((id) => noteMap.get(id))
    .filter((n): n is NoteListItem => n !== undefined);

  const hasContent =
    !!entity.description || incidentRelations.length > 0 || sourceNotes.length > 0;

  return (
    <aside
      ref={panelRef as React.Ref<HTMLElement>}
      role="complementary"
      aria-label="Entity panel"
      tabIndex={-1}
      className="lrn-panel lrn-panel--open"
    >
      {/* Header */}
      <div className="lrn-panel__header">
        <h2 className="lrn-panel__title">{entity.label}</h2>
        <button
          aria-label="Close entity panel"
          onClick={onClose}
          className="lrn-panel__close"
        >
          <X size={16} />
        </button>
      </div>

      {/* Body */}
      <div className="lrn-panel__body">
        {!hasContent && (
          <p className="lrn-panel__empty">No additional information available.</p>
        )}

        {entity.description && (
          <section className="lrn-panel__section">
            <h3 className="lrn-panel__section-title">Description</h3>
            <p className="lrn-panel__text">{entity.description}</p>
          </section>
        )}

        {incidentRelations.length > 0 && (
          <section className="lrn-panel__section">
            <h3 className="lrn-panel__section-title">Relations</h3>
            <ul className="lrn-panel__list">
              {incidentRelations.map((r, i) => (
                <li key={i} className="lrn-panel__list-item">
                  <span className="lrn-panel__relation-label">{r.label}</span>
                  {r.weight !== undefined && (
                    <span className="lrn-panel__relation-weight">
                      {r.weight.toFixed(2)}
                    </span>
                  )}
                </li>
              ))}
            </ul>
          </section>
        )}

        {sourceNotes.length > 0 && (
          <section className="lrn-panel__section">
            <h3 className="lrn-panel__section-title">Source Notes</h3>
            <ul className="lrn-panel__list">
              {sourceNotes.map((n) => (
                <li key={n.id}>
                  <button
                    onClick={() => onNavigateToNote(n.id)}
                    className="lrn-panel__note-link"
                  >
                    {n.title}
                  </button>
                </li>
              ))}
            </ul>
          </section>
        )}
      </div>
    </aside>
  );
}
