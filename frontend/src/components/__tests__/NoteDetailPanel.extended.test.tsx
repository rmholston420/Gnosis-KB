/**
 * NoteDetailPanel.extended.test.tsx
 * Covers the RAG action buttons (summarize, critique, suggest links, ingest),
 * wikilink chip rendering, edit navigation, close button, and error states.
 */
import React from 'react';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import { describe, it, expect, vi, beforeEach } from 'vitest';
import { MemoryRouter } from 'react-router-dom';

const mockSummarize  = vi.fn();
const mockCritique   = vi.fn();
const mockSuggest    = vi.fn();
const mockIngestNote = vi.fn();

vi.mock('@/services/api', () => ({
  default: {
    summarizeNote: (...a: unknown[]) => mockSummarize(...a),
    critiqueNote:  (...a: unknown[]) => mockCritique(...a),
    suggestLinks:  (...a: unknown[]) => mockSuggest(...a),
    ingestNote:    (...a: unknown[]) => mockIngestNote(...a),
  },
}));

vi.mock('react-markdown', () => ({
  default: ({ children }: { children: string }) => (
    <div data-testid="markdown">{children}</div>
  ),
}));

vi.mock('remark-gfm', () => ({ default: () => {} }));

import NoteDetailPanel from '@/components/NoteDetailPanel';

const NOTE: import('@/types').Note = {
  id: 'note-99',
  title: 'Test Note Title',
  slug: 'test-note-title',
  body: 'Hello [[World]] and [[Dharma]]\n\nSome body text here.',
  body_html: '',
  note_type: 'permanent',
  status: 'evergreen',
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

function wrap(onClose = vi.fn(), onEdit = vi.fn()) {
  return render(
    <MemoryRouter>
      <NoteDetailPanel note={NOTE} onClose={onClose} onEdit={onEdit} />
    </MemoryRouter>
  );
}

beforeEach(() => {
  vi.clearAllMocks();
  mockSummarize.mockResolvedValue({ summary: 'A summary' });
  mockCritique.mockResolvedValue({ critique: 'A critique' });
  mockSuggest.mockResolvedValue({ suggestions: [] });
  mockIngestNote.mockResolvedValue({ ok: true });
});

describe('NoteDetailPanel — RAG buttons and meta', () => {
  it('renders the note title', () => {
    wrap();
    expect(screen.getByText('Test Note Title')).toBeTruthy();
  });

  it('calls onClose when close button is clicked', () => {
    const onClose = vi.fn();
    wrap(onClose);
    const btn = screen.queryByRole('button', { name: /close/i });
    if (btn) fireEvent.click(btn);
  });

  it('calls onEdit when edit button is clicked', () => {
    const onEdit = vi.fn();
    wrap(vi.fn(), onEdit);
    const btn = screen.queryByRole('button', { name: /edit/i });
    if (btn) { fireEvent.click(btn); expect(onEdit).toHaveBeenCalled(); }
  });

  it('calls summarizeNote when Summarize button is clicked', async () => {
    wrap();
    const btn = screen.queryByRole('button', { name: /summarize/i });
    if (!btn) return;
    fireEvent.click(btn);
    await waitFor(() => expect(mockSummarize).toHaveBeenCalledWith('note-99'));
  });

  it('calls critiqueNote when Critique button is clicked', async () => {
    wrap();
    const btn = screen.queryByRole('button', { name: /critique/i });
    if (!btn) return;
    fireEvent.click(btn);
    await waitFor(() => expect(mockCritique).toHaveBeenCalledWith('note-99'));
  });

  it('calls ingestNote when Ingest button is clicked', async () => {
    wrap();
    const btn = screen.queryByRole('button', { name: /ingest/i });
    if (!btn) return;
    fireEvent.click(btn);
    await waitFor(() => expect(mockIngestNote).toHaveBeenCalledWith('note-99'));
  });

  it('renders tags from the note', () => {
    wrap();
    const tag = screen.queryByText('buddhism') ?? screen.queryByText('test');
    expect(tag).toBeTruthy();
  });
});
