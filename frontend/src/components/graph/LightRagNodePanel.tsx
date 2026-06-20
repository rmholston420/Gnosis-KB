/**
 * LightRagNodePanel
 * =================
 * Slide-in right-side panel shown when a node in the LightRAG Knowledge Graph
 * is clicked.  Displays:
 *   - Entity name and description
 *   - Relation list (subject → predicate → object) for edges incident to this node
 *   - Links to source notes that contributed the entity (if available)
 *
 * Props
 * -----
 *   entity: LightRagEntity | null  — the clicked entity (null = panel hidden)
 *   relations: LightRagRelation[]  — all relations from the graph data
 *   notes: NoteListItem[]          — all notes (used to resolve source_note_ids)
 *   onClose: () => void
 *   onNavigateToNote: (noteId: string) => void
 */

import React, { useEffect, useRef } from 'react';
import './LightRagNodePanel.css';

export interface LightRagEntity {
  id: string;
  label: string;
  description?: string;
  cluster?: number;
  source_note_ids?: string[];
}

export interface LightRagRelation {
  source: string;
  target: string;
  label?: string;
  weight?: number;
}

export interface NoteListItem {
  id: string;
  title: string;
  folder?: string;
}

interface Props {
  entity: LightRagEntity | null;
  relations: LightRagRelation[];
  notes: NoteListItem[];
  onClose: () => void;
  onNavigateToNote: (noteId: string) => void;
}

export function LightRagNodePanel({
  entity,
  relations,
  notes,
  onClose,
  onNavigateToNote,
}: Props) {
  const panelRef = useRef<HTMLDivElement | null>(null);

  // Close on Escape
  useEffect(() => {
    function handleKey(e: KeyboardEvent) {
      if (e.key === 'Escape') onClose();
    }
    window.addEventListener('keydown', handleKey);
    return () => window.removeEventListener('keydown', handleKey);
  }, [onClose]);

  // Focus panel for a11y when opened
  useEffect(() => {
    if (entity && panelRef.current) {
      panelRef.current.focus();
    }
  }, [entity]);

  if (!entity) return null;

  const incidentRelations = relations.filter(
    (r) => r.source === entity.id || r.target === entity.id
  );

  const sourceNotes = (entity.source_note_ids ?? []).flatMap((nid) => {
    const n = notes.find((note) => note.id === nid);
    return n ? [n] : [];
  });

  return (
    <div
      className={`lrn-panel ${entity ? 'lrn-panel--open' : ''}`}
      ref={panelRef}
      tabIndex={-1}
      role="complementary"
      aria-label={`Entity panel: ${entity.label}`}
    >
      <div className="lrn-header">
        <h2 className="lrn-title">{entity.label}</h2>
        <button
          className="lrn-close"
          onClick={onClose}
          aria-label="Close entity panel"
        >
          ×
        </button>
      </div>

      {entity.description && (
        <section className="lrn-section">
          <h3 className="lrn-section-title">Description</h3>
          <p className="lrn-description">{entity.description}</p>
        </section>
      )}

      {incidentRelations.length > 0 && (
        <section className="lrn-section">
          <h3 className="lrn-section-title">Relations ({incidentRelations.length})</h3>
          <ul className="lrn-relations" role="list">
            {incidentRelations.map((r, i) => (
              <li key={i} className="lrn-relation">
                <span className="lrn-rel-src">{r.source === entity.id ? entity.label : r.source}</span>
                <span className="lrn-rel-pred">{r.label ?? '→'}</span>
                <span className="lrn-rel-tgt">{r.target === entity.id ? entity.label : r.target}</span>
              </li>
            ))}
          </ul>
        </section>
      )}

      {sourceNotes.length > 0 && (
        <section className="lrn-section">
          <h3 className="lrn-section-title">Source Notes</h3>
          <ul className="lrn-source-notes" role="list">
            {sourceNotes.map((note) => (
              <li key={note.id}>
                <button
                  className="lrn-note-link"
                  onClick={() => onNavigateToNote(note.id)}
                >
                  {note.title}
                  {note.folder && (
                    <span className="lrn-note-folder">{note.folder}</span>
                  )}
                </button>
              </li>
            ))}
          </ul>
        </section>
      )}

      {incidentRelations.length === 0 && !entity.description && (
        <div className="lrn-empty">
          <p>No additional information stored for this entity yet.</p>
          <p className="lrn-empty-hint">Ingest more notes to enrich the graph.</p>
        </div>
      )}
    </div>
  );
}

export default LightRagNodePanel;
