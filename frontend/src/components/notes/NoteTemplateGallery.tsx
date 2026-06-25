/**
 * NoteTemplateGallery
 * ===================
 * Modal/overlay shown when the user clicks "New Note".
 * The user picks a template; the parent receives it via onSelect.
 *
 * Templates are defined client-side — no backend endpoint is required.
 * Previously called api.listTemplates() which hit /notes/templates and
 * received a 404 because FastAPI's /notes/{id} catch-all treated
 * "templates" as a note ID.
 *
 * Props
 * -----
 *   onSelect(template) — called with the chosen template object
 *   onClose()          — called when the user cancels
 */

import React, { useEffect, useRef, useState } from 'react';
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

const BUILT_IN_TEMPLATES: NoteTemplate[] = [
  {
    id: 'blank',
    name: 'Blank Note',
    description: 'Start with a completely empty note.',
    note_type: 'permanent',
    folder: '10-zettelkasten',
    body: '',
    icon: 'file',
  },
  {
    id: 'permanent',
    name: 'Permanent Note',
    description: 'A fully developed idea in your own words — the core Zettelkasten atom.',
    note_type: 'permanent',
    folder: '10-zettelkasten',
    body: '## Idea\n\n\n\n## Context\n\n\n\n## Links\n\n- [[]]\n',
    icon: 'zap',
  },
  {
    id: 'literature',
    name: 'Literature Note',
    description: 'Capture key ideas from a book, article, or video with source attribution.',
    note_type: 'literature',
    folder: '20-literature',
    body: '## Source\n\n- **Title:**\n- **Author:**\n- **URL:**\n\n## Key Points\n\n\n\n## My Take\n\n',
    icon: 'book-open',
  },
  {
    id: 'fleeting',
    name: 'Fleeting Note',
    description: 'A quick capture for a passing thought — process it later.',
    note_type: 'fleeting',
    folder: '00-inbox',
    body: '<!-- Quick capture — develop this into a permanent note later -->\n\n',
    icon: 'file',
  },
  {
    id: 'moc',
    name: 'Map of Content',
    description: 'An index note that organises links to related permanent notes.',
    note_type: 'moc',
    folder: '30-moc',
    body: '## Overview\n\n\n\n## Notes\n\n- [[]]\n- [[]]\n- [[]]\n\n## Questions\n\n',
    icon: 'map',
  },
  {
    id: 'daily',
    name: 'Daily Note',
    description: 'Journal template for daily reflections, tasks, and captures.',
    note_type: 'fleeting',
    folder: '00-inbox',
    body: '## Morning\n\n\n\n## Tasks\n\n- [ ] \n- [ ] \n\n## Evening Reflection\n\n',
    icon: 'sun',
  },
  {
    id: 'meeting',
    name: 'Meeting Note',
    description: 'Structured template for meetings with attendees, agenda, and action items.',
    note_type: 'permanent',
    folder: '40-projects',
    body: '## Meeting: \n\n**Date:** \n**Attendees:** \n\n## Agenda\n\n1. \n\n## Notes\n\n\n\n## Action Items\n\n- [ ] \n',
    icon: 'users',
  },
];

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
  const [activeId, setActiveId] = useState<string>(BUILT_IN_TEMPLATES[0].id);
  const dialogRef = useRef<HTMLDivElement | null>(null);

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

  const active = BUILT_IN_TEMPLATES.find((t) => t.id === activeId) ?? BUILT_IN_TEMPLATES[0];

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
          >\xD7</button>
        </div>

        <div className="template-gallery-body">
          <ul
            role="list"
            className="template-gallery-list"
            aria-label="Templates"
          >
            {BUILT_IN_TEMPLATES.map((t) => (
              <li
                key={t.id}
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
            <p className="template-gallery-preview-desc">{active.description}</p>
            {active.body ? (
              <pre className="template-gallery-preview-body">{active.body}</pre>
            ) : (
              <p className="template-gallery-preview-empty" style={{ fontStyle: 'italic' }}>
                Empty canvas — write anything.
              </p>
            )}
            <button
              className="template-gallery-use-btn"
              onClick={() => onSelect(active)}
            >
              Use this template
            </button>
          </div>
        </div>

        {/* Footer */}
        <div className="template-gallery-footer">
          <button
            className="template-gallery-blank-btn"
            onClick={() => onSelect(BUILT_IN_TEMPLATES[0])}
          >
            Start blank
          </button>
          <button
            className="template-gallery-cancel-btn"
            onClick={onClose}
          >
            Cancel
          </button>
        </div>
      </div>
    </div>
  );
}
