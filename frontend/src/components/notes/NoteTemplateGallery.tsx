/**
 * NoteTemplateGallery
 * ===================
 * Modal/overlay shown when the user clicks "New Note" and the
 * GET /notes/templates endpoint has returned results.  The user picks a
 * template; the parent receives it via onSelect and opens the editor with
 * the pre-filled body and metadata.
 *
 * Props
 * -----
 *   onSelect(template) — called with the chosen template object
 *   onClose()          — called when the user cancels
 */

import React, { useEffect, useRef, useState } from 'react';
import api from '../../services/api';
import './NoteTemplateGallery.css';

export interface NoteTemplate {
  id: string;
  name: string;
  description: string;
  note_type: string;
  folder: string;
  body: string;
  icon: string;
}

interface Props {
  onSelect: (template: NoteTemplate) => void;
  onClose: () => void;
}

// Map template icon strings to accessible Unicode emoji / text icons so we
// avoid an icon-library dependency in this component.
const ICON_MAP: Record<string, string> = {
  file: '\u{1F4C4}',
  zap: '\u26A1',
  'book-open': '\u{1F4D6}',
  layout: '\u{1F4CB}',
  map: '\u{1F5FA}',
  users: '\u{1F465}',
  sun: '\u2600\uFE0F',
};

export function NoteTemplateGallery({ onSelect, onClose }: Props) {
  const [templates, setTemplates] = useState<NoteTemplate[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [activeId, setActiveId] = useState<string | null>(null);
  const dialogRef = useRef<HTMLDivElement | null>(null);

  useEffect(() => {
    api.listTemplates()
      .then((data) => {
        setTemplates(data as NoteTemplate[]);
        if ((data as NoteTemplate[]).length > 0) {
          setActiveId((data as NoteTemplate[])[0].id);
        }
      })
      .catch((err) => setError(err.message))
      .finally(() => setLoading(false));
  }, []);

  // Close on Escape; trap focus inside modal
  useEffect(() => {
    function onKey(e: KeyboardEvent) {
      if (e.key === 'Escape') onClose();
    }
    window.addEventListener('keydown', onKey);
    dialogRef.current?.focus();
    return () => window.removeEventListener('keydown', onKey);
  }, [onClose]);

  const activeTemplate = templates.find((t) => t.id === activeId) ?? null;

  return (
    <div className="ntg-backdrop" onClick={(e) => { if (e.target === e.currentTarget) onClose(); }}>
      <div
        className="ntg-modal"
        role="dialog"
        aria-modal="true"
        aria-label="Choose a note template"
        ref={dialogRef}
        tabIndex={-1}
      >
        <div className="ntg-header">
          <h2 className="ntg-heading">Choose a Template</h2>
          <button className="ntg-close" onClick={onClose} aria-label="Close template gallery">×</button>
        </div>

        <div className="ntg-body">
          <aside className="ntg-sidebar" role="list">
            {loading && <p className="ntg-loading">Loading templates…</p>}
            {error && <p className="ntg-error">{error}</p>}
            {templates.map((tpl) => (
              <button
                key={tpl.id}
                role="listitem"
                className={`ntg-item ${activeId === tpl.id ? 'ntg-item--active' : ''}`}
                onClick={() => setActiveId(tpl.id)}
                onDoubleClick={() => onSelect(tpl)}
              >
                <span className="ntg-item-icon" aria-hidden="true">
                  {ICON_MAP[tpl.icon] ?? '\u{1F4C4}'}
                </span>
                <span className="ntg-item-label">{tpl.name}</span>
              </button>
            ))}
          </aside>

          <main className="ntg-preview">
            {activeTemplate ? (
              <>
                <div className="ntg-preview-header">
                  <span className="ntg-preview-icon" aria-hidden="true">
                    {ICON_MAP[activeTemplate.icon] ?? '\u{1F4C4}'}
                  </span>
                  <div>
                    <h3 className="ntg-preview-title">{activeTemplate.name}</h3>
                    <p className="ntg-preview-desc">{activeTemplate.description}</p>
                    <div className="ntg-preview-meta">
                      <span className="ntg-badge">{activeTemplate.note_type}</span>
                      <span className="ntg-badge ntg-badge--folder">{activeTemplate.folder}</span>
                    </div>
                  </div>
                </div>
                <pre className="ntg-body-preview">{activeTemplate.body || '(Blank)'}</pre>
              </>
            ) : (
              !loading && <p className="ntg-no-preview">Select a template to preview</p>
            )}
          </main>
        </div>

        <div className="ntg-footer">
          <button className="ntg-btn ntg-btn--ghost" onClick={onClose}>Cancel</button>
          <button
            className="ntg-btn ntg-btn--primary"
            disabled={!activeTemplate}
            onClick={() => activeTemplate && onSelect(activeTemplate)}
          >
            Use Template
          </button>
        </div>
      </div>
    </div>
  );
}

export default NoteTemplateGallery;
