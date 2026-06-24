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
  const [_loading, _setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [activeId, setActiveId] = useState<string | null>(null);
  const dialogRef = useRef<HTMLDivElement | null>(null);

  useEffect(() => {
    api.listTemplates()
      .then((data) => {
        const tpls = (data as unknown as NoteTemplate[]);
        setTemplates(tpls);
        _setLoading(false);
        if (tpls.length > 0) {
          setActiveId(tpls[0].id);
        }
      })
      .catch((err: unknown) => {
        _setLoading(false);
        setError(err instanceof Error ? err.message : 'Failed to load templates');
      });
  }, []);

  // Focus trap
  useEffect(() => {
    const el = dialogRef.current;
    if (!el) return;
    const focusable = el.querySelectorAll<HTMLElement>(
      'button, [href], input, select, textarea, [tabindex]:not([tabindex="-1"])'
    );
    focusable[0]?.focus();
    const handleKey = (e: KeyboardEvent) => {
      if (e.key === 'Escape') { onClose(); return; }
      if (e.key !== 'Tab') return;
      if (focusable.length === 0) return;
      const first = focusable[0];
      const last  = focusable[focusable.length - 1];
      if (e.shiftKey) {
        if (document.activeElement === first) { e.preventDefault(); last.focus(); }
      } else {
        if (document.activeElement === last)  { e.preventDefault(); first.focus(); }
      }
    };
    el.addEventListener('keydown', handleKey);
    return () => el.removeEventListener('keydown', handleKey);
  }, [onClose]);

  const active = templates.find((t) => t.id === activeId) ?? null;
  const loading = _loading;

  return (
    <div
      className="template-gallery-overlay"
      role="dialog"
      aria-modal="true"
      aria-label="Choose a note template"
      onClick={(e) => { if (e.target === e.currentTarget) onClose(); }}
    >
      <div ref={dialogRef} className="template-gallery-dialog">
        {/* Header */}
        <div className="template-gallery-header">
          <h2 className="template-gallery-title">Choose a template</h2>
          <button
            className="template-gallery-close"
            onClick={onClose}
            aria-label="Close template gallery"
          >×</button>
        </div>

        {loading && <p className="template-gallery-loading">Loading templates…</p>}
        {error   && <p className="template-gallery-error">{error}</p>}

        {!loading && !error && (
          <div className="template-gallery-body">
            {/* Sidebar: template list */}
            <ul className="template-gallery-list" role="listbox" aria-label="Templates">
              {templates.map((t) => (
                <li key={t.id}
                  role="option"
                  aria-selected={t.id === activeId}
                  className={`template-gallery-list-item${ t.id === activeId ? ' active' : '' }`}
                  onClick={() => setActiveId(t.id)}
                  onKeyDown={(e) => { if (e.key === 'Enter' || e.key === ' ') setActiveId(t.id); }}
                  tabIndex={0}
                >
                  <span className="template-gallery-icon" aria-hidden="true">
                    {ICON_MAP[t.icon] ?? '\u{1F4C4}'}
                  </span>
                  {t.name}
                </li>
              ))}
            </ul>

            {/* Preview panel */}
            <div className="template-gallery-preview">
              {active ? (
                <>
                  <p className="template-gallery-preview-desc">{active.description}</p>
                  <pre className="template-gallery-preview-body">{active.body}</pre>
                  <button
                    className="template-gallery-use-btn"
                    onClick={() => onSelect(active)}
                  >
                    Use this template
                  </button>
                </>
              ) : (
                <p className="template-gallery-preview-empty">Select a template to preview it.</p>
              )}
            </div>
          </div>
        )}

        {/* Blank note fallback */}
        {!loading && !error && (
          <div className="template-gallery-footer">
            <button
              className="template-gallery-blank-btn"
              onClick={() => onSelect({
                id: '__blank__',
                name: 'Blank',
                description: 'Start with an empty note.',
                note_type: 'permanent',
                folder: '10-zettelkasten',
                body: '',
                icon: 'file',
              })}
            >
              Start blank
            </button>
          </div>
        )}
      </div>
    </div>
  );
}
