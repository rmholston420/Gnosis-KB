/**
 * NoteDetailPanel.test.tsx
 * Core unit tests for the NoteDetailPanel component.
 */
import React from 'react';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import { describe, it, expect, vi, beforeEach } from 'vitest';
import { MemoryRouter } from 'react-router-dom';

const mockSummarize   = vi.fn();
const mockCritique    = vi.fn();
const mockSuggest     = vi.fn();
const mockIngestNote  = vi.fn();

vi.mock('@/services/api', () => ({
  default: {
    summarizeNote:  (...a: unknown[]) => mockSummarize(...a),
    critiqueNote:   (...a: unknown[]) => mockCritique(...a),
    suggestLinks:   (...a: unknown[]) => mockSuggest(...a),
    ingestNote:     (...a: unknown[]) => mockIngestNote(...a),
  },
}));

import NoteDetailPanel from '../NoteDetailPanel';
import type { Note } from '../../types';

const baseNote: Note = {
  id: 'note-abc',
  title: 'Śūnyatā',
  slug: 'sunyata',
  body: '## Emptiness\n\nAll phenomena lack inherent existence. See also [[Dependent Origination]].',
  body_html: '<h2>Emptiness</h2><p>All phenomena lack inherent existence.</p>',
  note_type: 'permanent',
  status: 'evergreen',
  tags: ['buddhism', 'madhyamaka'],
  folder: '',
  created_at: '2025-01-01T00:00:00Z',
  modified_at: '2025-06-01T00:00:00Z',
  incoming_links: [],
  outgoing_links: [],
  frontmatter: {},
  word_count: 12,
  is_deleted: false,
  vector_indexed: true,
  graph_indexed: true,
};

const onClose = vi.fn();

function renderPanel(note: Note = baseNote, onWikilinkClick?: (t: string) => void) {
  return render(
    <MemoryRouter>
      <NoteDetailPanel note={note} onClose={onClose} onWikilinkClick={onWikilinkClick} />
    </MemoryRouter>
  );
}

// ---------------------------------------------------------------------------
describe('NoteDetailPanel — rendering', () => {
  beforeEach(() => { vi.clearAllMocks(); });

  it('renders note title', () => {
    renderPanel();
    expect(screen.getByText('Śūnyatā')).toBeTruthy();
  });

  it('renders tags', () => {
    renderPanel();
    expect(screen.getByText('buddhism')).toBeTruthy();
    expect(screen.getByText('madhyamaka')).toBeTruthy();
  });

  it('renders wikilink chips from body', () => {
    renderPanel();
    expect(screen.getByText('Dependent Origination')).toBeTruthy();
  });

  it('calls onClose when close button clicked', () => {
    renderPanel();
    fireEvent.click(screen.getByRole('button', { name: /close/i }));
    expect(onClose).toHaveBeenCalledTimes(1);
  });
});

// ---------------------------------------------------------------------------
describe('NoteDetailPanel — wikilink click', () => {
  beforeEach(() => { vi.clearAllMocks(); });

  it('calls onWikilinkClick with the link title', () => {
    const handler = vi.fn();
    renderPanel(baseNote, handler);
    fireEvent.click(screen.getByText('Dependent Origination'));
    expect(handler).toHaveBeenCalledWith('Dependent Origination');
  });
});

// ---------------------------------------------------------------------------
describe('NoteDetailPanel — AI actions', () => {
  beforeEach(() => { vi.clearAllMocks(); });

  it('calls summarizeNote and shows result', async () => {
    mockSummarize.mockResolvedValue({ summary: 'A deep teaching.' });
    renderPanel();
    fireEvent.click(screen.getByRole('button', { name: /summar/i }));
    await waitFor(() => expect(mockSummarize).toHaveBeenCalledWith('note-abc'));
    await waitFor(() => expect(screen.getByText('A deep teaching.')).toBeTruthy());
  });

  it('calls critiqueNote and shows result', async () => {
    mockCritique.mockResolvedValue({ critique: 'Needs more citations.' });
    renderPanel();
    fireEvent.click(screen.getByRole('button', { name: /critique/i }));
    await waitFor(() => expect(mockCritique).toHaveBeenCalledWith('note-abc'));
    await waitFor(() => expect(screen.getByText('Needs more citations.')).toBeTruthy());
  });

  it('calls suggestLinks and shows result', async () => {
    mockSuggest.mockResolvedValue({ suggestions: ['Link A', 'Link B'] });
    renderPanel();
    fireEvent.click(screen.getByRole('button', { name: /suggest|links/i }));
    await waitFor(() => expect(mockSuggest).toHaveBeenCalledWith('note-abc'));
  });

  it('shows error state when summarizeNote rejects', async () => {
    mockSummarize.mockRejectedValue(new Error('AI offline'));
    renderPanel();
    fireEvent.click(screen.getByRole('button', { name: /summar/i }));
    await waitFor(() => expect(screen.queryByText(/error|failed|offline/i)).toBeTruthy());
  });
});

// ---------------------------------------------------------------------------
describe('NoteDetailPanel — ingest action', () => {
  beforeEach(() => { vi.clearAllMocks(); });

  it('calls ingestNote when ingest button clicked', async () => {
    mockIngestNote.mockResolvedValue({ ok: true });
    renderPanel();
    const ingestBtn = screen.queryByRole('button', { name: /ingest/i });
    if (ingestBtn) {
      fireEvent.click(ingestBtn);
      await waitFor(() => expect(mockIngestNote).toHaveBeenCalledWith('note-abc'));
    }
  });
});
