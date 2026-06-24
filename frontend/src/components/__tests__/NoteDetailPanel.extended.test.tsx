/**
 * NoteDetailPanel.extended.test.tsx
 * Covers the RAG action buttons (summarize, critique, suggest links, ingest),
 * wikilink chip rendering, edit navigation, close button, and error states
 * — lines 81–176 previously missed.
 */
import React from 'react';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import { describe, it, expect, vi, beforeEach } from 'vitest';
import { MemoryRouter } from 'react-router-dom';

// ---- API mock ---------------------------------------------------------------
const mockSummarize   = vi.fn();
const mockCritique    = vi.fn();
const mockSuggest     = vi.fn();
const mockIngestNote  = vi.fn();

vi.mock('@/services/api', () => ({
  default: {
    summarizeNote: (...a: unknown[]) => mockSummarize(...a),
    critiqueNote:  (...a: unknown[]) => mockCritique(...a),
    suggestLinks:  (...a: unknown[]) => mockSuggest(...a),
    ingestNote:    (...a: unknown[]) => mockIngestNote(...a),
  },
}));

// react-markdown stub — keeps DOM simple
vi.mock('react-markdown', () => ({
  default: ({ children }: { children: string }) => (
    <div data-testid="markdown">{children}</div>
  ),
}));

vi.mock('remark-gfm', () => ({ default: () => {} }));

// Static import — vi.mock() calls above are hoisted by Vitest so mocks are
// already in place when this module is resolved.
import NoteDetailPanel from '@/components/NoteDetailPanel';

const NOTE = {
  id: 'note-99',
  title: 'Test Note Title',
  slug: 'test-note-title',
  body: 'Hello [[World]] and [[Dharma]]\n\nSome body text here.',
  body_html: '',
  note_type: 'permanent' as const,
  status: 'evergreen' as const,
  folder: '10-zettelkasten',
  word_count: 8,
  is_deleted: false,
  vector_indexed: true,
  graph_indexed: false,
  tags: ['buddhism', 'test'],
  created_at: '2026-01-01T00:00:00Z',
  modified_at: '2026-06-01T00:00:00Z',
  frontmatter: {},
  outgoing_links: [],
  incoming_links: [],
};
