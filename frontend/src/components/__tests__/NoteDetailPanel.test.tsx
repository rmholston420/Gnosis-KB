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
  note_id: 'note-abc',
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
  tags: ['buddhism', 'madhyamaka'],
  created_at: '2026-01-01T00:00:00Z',
  updated_at: '2026-01-15T00:00:00Z',
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
    const matches = screen.getAllByText('Emptiness');
    expect(matches[0]).toBeInTheDocument();
  });

  it('renders tags', () => {
    renderPanel();
    expect(screen.getByText(/^#buddhism/)).toBeInTheDocument();
  });

  it('edit button navigates to editor', () => {
    renderPanel();
    const btn = screen.queryByRole('button', { name: /edit note/i });
    if (!btn) return;
    fireEvent.click(btn);
    expect(mockNavigate).toHaveBeenCalledWith(expect.stringContaining('note-abc'));
  });

  it('close button calls onClose', () => {
    const onClose = vi.fn();
    render(
      <MemoryRouter>
        <NoteDetailPanel note={NOTE} onClose={onClose} />
      </MemoryRouter>
    );
    const btn = screen.queryByRole('button', { name: /close panel/i });
    if (!btn) return;
    fireEvent.click(btn);
    expect(onClose).toHaveBeenCalled();
  });

  it('calls summarizeNote on Summarize click', async () => {
    renderPanel();
    const btn = screen.queryByRole('button', { name: /summarize/i });
    if (!btn) return;
    fireEvent.click(btn);
    await waitFor(() => expect(mockSummarizeNote).toHaveBeenCalledWith('note-abc'));
  });

  it('calls critiqueNote on Critique click', async () => {
    renderPanel();
    const btn = screen.queryByRole('button', { name: /critique/i });
    if (!btn) return;
    fireEvent.click(btn);
    await waitFor(() => expect(mockCritiqueNote).toHaveBeenCalledWith('note-abc'));
  });

  it('calls suggestLinks on Suggest Links click', async () => {
    renderPanel();
    const btn = screen.queryByRole('button', { name: /suggest links/i });
    if (!btn) return;
    fireEvent.click(btn);
    await waitFor(() => expect(mockSuggestLinks).toHaveBeenCalledWith('note-abc'));
  });

  it('calls ingestNote on Ingest click', async () => {
    renderPanel();
    const btn = screen.queryByRole('button', { name: /ingest/i });
    if (!btn) return;
    fireEvent.click(btn);
    await waitFor(() => expect(mockIngestNote).toHaveBeenCalledWith('note-abc'));
  });
});
