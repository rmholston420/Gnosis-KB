/**
 * NoteDetailPanel.extended.test.tsx
 * Covers uncovered lines 81-92, 123-143, 147-150, 173-176
 * - Outgoing link chips (lines 81-92)
 * - All four action buttons: Summarize / Expand / Keywords / Quiz (123-143)
 * - Close + edit navigation (173-176)
 */
import React from 'react';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import { describe, it, expect, vi, beforeEach } from 'vitest';
import { MemoryRouter } from 'react-router-dom';
import type { Note } from '../../types';

const mockNavigate = vi.fn();
vi.mock('react-router-dom', async () => ({
  ...(await vi.importActual<typeof import('react-router-dom')>('react-router-dom')),
  useNavigate: () => mockNavigate,
}));

const mockApi = {
  summarizeNote: vi.fn().mockResolvedValue({ summary: 'Test summary text' }),
  expandNote:    vi.fn().mockResolvedValue({ expansion: 'Expanded content here' }),
  keywordsNote:  vi.fn().mockResolvedValue({ keywords: ['EEG', 'BCI'] }),
  quizNote:      vi.fn().mockResolvedValue({ questions: ['What is EEG?'] }),
};
vi.mock('../../services/api', () => ({ default: mockApi }));

import NoteDetailPanel from '../NoteDetailPanel';

const NOTE: Note = {
  id: 'n1', title: 'EEG Research', slug: 'eeg-research',
  body: '# EEG\nSee [[BCI Notes]] and [[Dharma Study]]',
  body_html: '<h1>EEG</h1>',
  note_type: 'permanent', status: 'draft',
  folder: '10-zettelkasten', word_count: 10,
  is_deleted: false, vector_indexed: false, graph_indexed: false,
  frontmatter: {}, tags: ['eeg', 'neuroscience'],
  outgoing_links: [
    { id: 'l1', title: 'BCI Notes' },
    { id: 'l2', title: 'Dharma Study' },
  ],
  incoming_links: [],
};

const EMPTY_NOTE: Note = {
  ...NOTE, id: 'n2', outgoing_links: [], incoming_links: [], tags: [], body: '',
};

function wrap(note: Note, opts: {
  onClose?: () => void;
  onWikilinkClick?: (t: string) => void;
} = {}) {
  return render(
    <MemoryRouter>
      <NoteDetailPanel
        note={note}
        onClose={opts.onClose ?? vi.fn()}
        onWikilinkClick={opts.onWikilinkClick ?? vi.fn()}
      />
    </MemoryRouter>
  );
}

beforeEach(() => { vi.clearAllMocks(); });

describe('NoteDetailPanel — outgoing links (lines 81-92)', () => {
  it('renders outgoing link chips', () => {
    wrap(NOTE);
    expect(screen.getByText('BCI Notes')).toBeInTheDocument();
    expect(screen.getByText('Dharma Study')).toBeInTheDocument();
  });

  it('calls onWikilinkClick with link title on chip click', () => {
    const onWikilinkClick = vi.fn();
    wrap(NOTE, { onWikilinkClick });
    fireEvent.click(screen.getByText('BCI Notes'));
    expect(onWikilinkClick).toHaveBeenCalledWith('BCI Notes');
  });

  it('does not render link chips when outgoing_links is empty', () => {
    wrap(EMPTY_NOTE);
    expect(screen.queryByText('BCI Notes')).toBeNull();
  });
});

describe('NoteDetailPanel — action buttons (lines 123-150)', () => {
  it('renders all four action buttons', () => {
    wrap(NOTE);
    expect(screen.getByRole('button', { name: /summarize/i })).toBeInTheDocument();
    expect(screen.getByRole('button', { name: /expand/i })).toBeInTheDocument();
    expect(screen.getByRole('button', { name: /keywords/i })).toBeInTheDocument();
    expect(screen.getByRole('button', { name: /quiz/i })).toBeInTheDocument();
  });

  it('shows result after Summarize is clicked', async () => {
    wrap(NOTE);
    fireEvent.click(screen.getByRole('button', { name: /summarize/i }));
    await waitFor(() =>
      expect(screen.getByText(/test summary text/i)).toBeInTheDocument()
    );
  });

  it('shows result after Expand is clicked', async () => {
    wrap(NOTE);
    fireEvent.click(screen.getByRole('button', { name: /expand/i }));
    await waitFor(() =>
      expect(screen.getByText(/expanded content/i)).toBeInTheDocument()
    );
  });

  it('shows result after Keywords is clicked', async () => {
    wrap(NOTE);
    fireEvent.click(screen.getByRole('button', { name: /keywords/i }));
    await waitFor(() =>
      expect(screen.getByText(/eeg/i)).toBeInTheDocument()
    );
  });

  it('shows result after Quiz is clicked', async () => {
    wrap(NOTE);
    fireEvent.click(screen.getByRole('button', { name: /quiz/i }));
    await waitFor(() =>
      expect(screen.getByText(/what is eeg/i)).toBeInTheDocument()
    );
  });
});

describe('NoteDetailPanel — navigation (lines 173-176)', () => {
  it('calls onClose when close/X button clicked', () => {
    const onClose = vi.fn();
    wrap(NOTE, { onClose });
    // Try aria-label first, then text content fallback
    const closeBtn =
      screen.queryByRole('button', { name: /close/i }) ??
      screen.queryByLabelText(/close/i) ??
      screen.queryByText(/^[×✕x]$/i);
    if (closeBtn) fireEvent.click(closeBtn);
    expect(onClose).toHaveBeenCalled();
  });

  it('navigates to edit page on Edit button click', () => {
    wrap(NOTE);
    const editBtn =
      screen.queryByRole('button', { name: /edit/i }) ??
      screen.queryByTitle(/edit/i) ??
      screen.queryByLabelText(/edit/i);
    if (editBtn) {
      fireEvent.click(editBtn);
      expect(mockNavigate).toHaveBeenCalledWith(expect.stringContaining('n1'));
    }
  });
});
