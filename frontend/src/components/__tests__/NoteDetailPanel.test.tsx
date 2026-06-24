/**
 * NoteDetailPanel.test.tsx
 *
 * The component now accepts `note: Note` (full object) instead of
 * `noteId: string`. Internal fetch was removed; the parent resolves
 * the note and passes it directly.
 *
 * API methods are now named:
 *   api.summarizeNote(id)  — was api.summarize(id)
 *   api.critiqueNote(id)   — was api.critique(id)
 *   api.ingestNote(id)     — was api.ingest(id)
 *   api.suggestLinks(id)   — unchanged
 *
 * Edit button: title="Edit note"  → aria-label /edit note/i
 * Close button: title="Close panel" → aria-label /close panel/i
 *
 * Tags render as "#buddhism" (with hash prefix) — use /^#buddhism/ regex.
 */
import React from 'react';
import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';

const mockSummarizeNote = vi.fn();
const mockCritiqueNote  = vi.fn();
const mockSuggestLinks  = vi.fn();
const mockIngestNote    = vi.fn();

vi.mock('@/services/api', () => ({
  default: {
    summarizeNote: (...a: unknown[]) => mockSummarizeNote(...a),
    critiqueNote:  (...a: unknown[]) => mockCritiqueNote(...a),
    suggestLinks:  (...a: unknown[]) => mockSuggestLinks(...a),
    ingestNote:    (...a: unknown[]) => mockIngestNote(...a),
    listNotes:     vi.fn().mockResolvedValue({ items: [] }),
  },
}));

const mockNavigate = vi.fn();
vi.mock('react-router-dom', async (orig) => {
  const actual = await orig<typeof import('react-router-dom')>();
  return { ...actual, useNavigate: () => mockNavigate };
});

import NoteDetailPanel from '@/components/NoteDetailPanel';
import type { Note } from '@/types';

const NOTE: Note = {
  id: 'note-abc',
  title: 'Emptiness',
  slug: 'emptiness',
  body: '## Emptiness\n\nAll phenomena lack inherent existence. See also [[Dependent Origination]].',
  body_html: '',
  note_type: 'permanent',
  status: 'evergreen',
  folder: '10-zettelkasten',
  word_count: 12,
  is_deleted: false,
  vector_indexed: true,
  graph_indexed: false,
  tags: ['buddhism', 'madhyamaka'],
  created_at: '2026-01-01T00:00:00Z',
  modified_at: '2026-01-15T00:00:00Z',
  frontmatter: {},
  outgoing_links: [],
  incoming_links: [],
};

// Component no longer accepts onEdit — Edit button calls useNavigate internally.
function renderPanel() {
  return render(
    <MemoryRouter>
      <NoteDetailPanel note={NOTE} onClose={vi.fn()} />
    </MemoryRouter>
  );
}

beforeEach(() => {
  vi.clearAllMocks();
  mockSummarizeNote.mockResolvedValue({ summary: 'All is empty.' });
  mockCritiqueNote.mockResolvedValue({
    overall: 'Needs more citations.',
    strengths: [],
    weaknesses: [],
    suggestions: [],
  });
  mockSuggestLinks.mockResolvedValue({ suggestions: [] });
  mockIngestNote.mockResolvedValue({});
});

describe('NoteDetailPanel', () => {
  it('renders note title', () => {
    renderPanel();
    // The title "Emptiness" appears twice: once in the panel header <h2> and
    // once inside the rendered markdown body <h2>. Use getAllByText and assert
    // the first instance (the panel header) is present.
    const matches = screen.getAllByText('Emptiness');
    expect(matches[0]).toBeInTheDocument();
  });

  it('renders tags', () => {
    renderPanel();
    // Tags render as "#buddhism" with hash prefix
    expect(screen.getByText(/^#buddhism/)).toBeInTheDocument();
  });

  it('renders body content', () => {
    renderPanel();
    expect(
      screen.getByText(/all phenomena lack inherent existence/i)
    ).toBeInTheDocument();
  });

  it('renders wikilinks in body', () => {
    renderPanel();
    expect(screen.getByText('Dependent Origination')).toBeInTheDocument();
  });

  it('calls api.critiqueNote when Critique button clicked', async () => {
    renderPanel();
    fireEvent.click(screen.getByRole('button', { name: /critique/i }));
    await waitFor(() =>
      expect(mockCritiqueNote).toHaveBeenCalledWith('note-abc')
    );
  });

  it('calls api.summarizeNote when Summarize button clicked', async () => {
    renderPanel();
    fireEvent.click(screen.getByRole('button', { name: /summarize/i }));
    await waitFor(() =>
      expect(mockSummarizeNote).toHaveBeenCalledWith('note-abc')
    );
  });

  it('calls onEdit (navigate) when Edit button clicked', () => {
    renderPanel();
    fireEvent.click(screen.getByRole('button', { name: /edit note/i }));
    expect(mockNavigate).toHaveBeenCalledWith('/notes/note-abc');
  });

  it('calls onClose when Close button clicked', () => {
    const onClose = vi.fn();
    render(
      <MemoryRouter>
        <NoteDetailPanel note={NOTE} onClose={onClose} />
      </MemoryRouter>
    );
    fireEvent.click(screen.getByRole('button', { name: /close panel/i }));
    expect(onClose).toHaveBeenCalled();
  });
});
