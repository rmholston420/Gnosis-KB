/**
 * NoteDetailPanel.extended.test.tsx
 * NoteDetailPanel takes a `note: Note` prop directly (not noteId).
 * note.body is the field read by extractWikilinks (not note.content).
 */
import React from 'react';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import { describe, it, expect, vi, beforeEach } from 'vitest';
import { MemoryRouter } from 'react-router-dom';
import NoteDetailPanel from '@/components/NoteDetailPanel';

const mockSummarizeNote = vi.fn();
const mockCritiqueNote = vi.fn();
const mockSuggestLinks = vi.fn();
const mockIngestNote = vi.fn();

vi.mock('@/services/api', () => ({
  default: {
    summarizeNote: (...a: unknown[]) => mockSummarizeNote(...a),
    critiqueNote:  (...a: unknown[]) => mockCritiqueNote(...a),
    suggestLinks:  (...a: unknown[]) => mockSuggestLinks(...a),
    ingestNote:    (...a: unknown[]) => mockIngestNote(...a),
  },
}));

/** Minimal Note fixture matching the actual Note type used by NoteDetailPanel */
const NOTE = {
  id: 'note-1',
  title: 'Detail Note',
  body: 'Some **content** here. Links to [[Alpha]] and [[Beta|Alias]].',
  tags: ['dharma', 'practice'],
  note_type: 'standard',
  status: 'active',
  folder: 'Teachings',
  word_count: 12,
  updated_at: new Date().toISOString(),
};

function setup(overrides: Partial<typeof NOTE> = {}, extraProps: Record<string, unknown> = {}) {
  const note = { ...NOTE, ...overrides };
  return render(
    <MemoryRouter>
      <NoteDetailPanel note={note as any} onClose={vi.fn()} {...extraProps} />
    </MemoryRouter>
  );
}

describe('NoteDetailPanel extended', () => {
  beforeEach(() => vi.clearAllMocks());

  it('renders note title', () => {
    setup();
    expect(screen.getByText('Detail Note')).toBeTruthy();
  });

  it('renders tags', () => {
    setup();
    expect(screen.getByText('#dharma')).toBeTruthy();
  });

  it('renders wikilink chips from body', () => {
    setup();
    expect(screen.getByText('Alpha')).toBeTruthy();
  });

  it('renders wikilink alias correctly', () => {
    setup();
    expect(screen.getByText('Alias')).toBeTruthy();
  });

  it('renders note with no tags without crashing', () => {
    setup({ tags: [] });
    expect(screen.getByText('Detail Note')).toBeTruthy();
  });

  it('renders note with no wikilinks without crashing', () => {
    setup({ body: 'Plain body text, no links.' });
    expect(screen.getByText('Detail Note')).toBeTruthy();
  });

  it('calls onClose when close button is clicked', () => {
    const onClose = vi.fn();
    render(
      <MemoryRouter>
        <NoteDetailPanel note={NOTE as any} onClose={onClose} />
      </MemoryRouter>
    );
    const closeBtn = screen.getByTitle('Close panel');
    fireEvent.click(closeBtn);
    expect(onClose).toHaveBeenCalled();
  });

  it('edit button is present with correct title', () => {
    setup();
    expect(screen.getByTitle('Edit note')).toBeTruthy();
  });

  it('summarize button triggers summarizeNote API call', async () => {
    mockSummarizeNote.mockResolvedValue({ summary: 'A nice summary.' });
    setup();
    fireEvent.click(screen.getByText('Summarize'));
    await waitFor(() => expect(mockSummarizeNote).toHaveBeenCalledWith('note-1'));
    await waitFor(() => expect(screen.getByText('A nice summary.')).toBeTruthy());
  });

  it('critique button triggers critiqueNote API call', async () => {
    mockCritiqueNote.mockResolvedValue({
      overall: 'Good note.',
      strengths: ['Clear'],
      weaknesses: [],
      suggestions: [],
    });
    setup();
    fireEvent.click(screen.getByText('Critique'));
    await waitFor(() => expect(mockCritiqueNote).toHaveBeenCalledWith('note-1'));
  });

  it('suggest links button triggers suggestLinks API call', async () => {
    mockSuggestLinks.mockResolvedValue({ suggestions: [{ title: 'Dharma', reason: 'Related' }] });
    setup();
    fireEvent.click(screen.getByText('Suggest Links'));
    await waitFor(() => expect(mockSuggestLinks).toHaveBeenCalledWith('note-1'));
  });

  it('ingest button triggers ingestNote API call', async () => {
    mockIngestNote.mockResolvedValue({});
    setup();
    fireEvent.click(screen.getByText('Ingest'));
    await waitFor(() => expect(mockIngestNote).toHaveBeenCalledWith('note-1'));
  });

  it('action error state shows error message', async () => {
    mockSummarizeNote.mockRejectedValue(new Error('fail'));
    setup();
    fireEvent.click(screen.getByText('Summarize'));
    await waitFor(() => expect(screen.getByText(/error occurred/i)).toBeTruthy());
  });

  it('result dismiss button clears result', async () => {
    mockSummarizeNote.mockResolvedValue({ summary: 'Summary text.' });
    setup();
    fireEvent.click(screen.getByText('Summarize'));
    await waitFor(() => screen.getByText('Summary text.'));
    fireEvent.click(screen.getByText('\u00d7'));
    expect(screen.queryByText('Summary text.')).toBeNull();
  });

  it('onWikilinkClick fires when chip is clicked', () => {
    const onWikilinkClick = vi.fn();
    render(
      <MemoryRouter>
        <NoteDetailPanel note={NOTE as any} onClose={vi.fn()} onWikilinkClick={onWikilinkClick} />
      </MemoryRouter>
    );
    fireEvent.click(screen.getByText('Alpha'));
    expect(onWikilinkClick).toHaveBeenCalledWith('Alpha');
  });
});
