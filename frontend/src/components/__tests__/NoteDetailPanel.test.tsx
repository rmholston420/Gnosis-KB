/**
 * NoteDetailPanel.test.tsx
 * ========================
 * NoteDetailPanel is a CONTROLLED component — it receives `note` and
 * `onClose` as props; it does NOT fetch internally.  All tests pass a
 * pre-built Note fixture directly.
 *
 * Cases:
 *  1.  Renders note title
 *  2.  Renders note_type in the header meta line
 *  3.  Renders tags as chips
 *  4.  Does NOT render tag chips when tags array is empty
 *  5.  Renders markdown body content
 *  6.  Renders wikilink chips for [[wikilinks]] found in the body
 *  7.  Clicking a wikilink chip calls onWikilinkClick with the title
 *  8.  Clicking the Edit (pencil) button navigates to /notes/:id
 *  9.  Clicking the Close (X) button calls onClose
 * 10.  Does NOT render action result section when result is null
 *      (checked via data-testid on the result container, not button labels)
 * 11.  All four action buttons render
 * 12.  Action result appears after clicking Summarize
 */
import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import NoteDetailPanel from '../NoteDetailPanel';
import type { Note } from '../../types';

const mockNavigate = vi.fn();
vi.mock('react-router-dom', async () => {
  const actual = await vi.importActual<typeof import('react-router-dom')>('react-router-dom');
  return { ...actual, useNavigate: () => mockNavigate };
});

// Minimal api stubs — the panel calls these only when action buttons are clicked
vi.mock('../../services/api', () => ({
  default: {
    summarizeNote: vi.fn().mockResolvedValue({ summary: 'A summary.' }),
    critiqueNote:  vi.fn().mockResolvedValue({ overall: 'Good note.' }),
    suggestLinks:  vi.fn().mockResolvedValue({ suggestions: [] }),
    ingestNote:    vi.fn().mockResolvedValue({}),
  },
}));

const baseNote: Note = {
  id:            'note-abc',
  title:         'Śūnyatā',
  slug:          'sunyata',
  body:          '## Emptiness\n\nAll phenomena lack inherent existence. See also [[Dependent Origination]].',
  note_type:     'permanent',
  status:        'active',
  tags:          ['buddhism', 'madhyamaka'],
  folder:        null,
  created_at:    '2025-01-01T00:00:00Z',
  updated_at:    '2025-06-01T00:00:00Z',
  incoming_links: [],
  outgoing_links: [],
  word_count:    12,
};

const onClose = vi.fn();

function renderPanel(note: Note = baseNote, onWikilinkClick?: (t: string) => void) {
  return render(
    <MemoryRouter>
      <NoteDetailPanel
        note={note}
        onClose={onClose}
        onWikilinkClick={onWikilinkClick}
      />
    </MemoryRouter>
  );
}

beforeEach(() => {
  onClose.mockReset();
  mockNavigate.mockReset();
});

describe('NoteDetailPanel', () => {
  it('renders the note title', () => {
    renderPanel();
    expect(screen.getByText('Śūnyatā')).toBeInTheDocument();
  });

  it('renders note_type in the header meta', () => {
    renderPanel();
    expect(screen.getByText('permanent')).toBeInTheDocument();
  });

  it('renders tags as chips', () => {
    renderPanel();
    expect(screen.getByText('#buddhism')).toBeInTheDocument();
    expect(screen.getByText('#madhyamaka')).toBeInTheDocument();
  });

  it('does not render tag section when tags is empty', () => {
    renderPanel({ ...baseNote, tags: [] });
    expect(screen.queryByText('#buddhism')).not.toBeInTheDocument();
  });

  it('renders markdown body heading', async () => {
    renderPanel();
    expect(await screen.findByRole('heading', { name: /emptiness/i })).toBeInTheDocument();
  });

  it('renders wikilink chip for [[Dependent Origination]]', async () => {
    renderPanel();
    expect(await screen.findByText('Dependent Origination')).toBeInTheDocument();
  });

  it('calls onWikilinkClick when a wikilink chip is clicked', async () => {
    const onWikilinkClick = vi.fn();
    renderPanel(baseNote, onWikilinkClick);
    const chip = await screen.findByText('Dependent Origination');
    const btn = chip.closest('button') as HTMLButtonElement;
    fireEvent.click(btn);
    expect(onWikilinkClick).toHaveBeenCalledWith('Dependent Origination');
  });

  it('clicking the Edit button navigates to /notes/:id', () => {
    renderPanel();
    fireEvent.click(screen.getByTitle('Edit note'));
    expect(mockNavigate).toHaveBeenCalledWith('/notes/note-abc');
  });

  it('clicking the Close button calls onClose', () => {
    renderPanel();
    fireEvent.click(screen.getByTitle('Close panel'));
    expect(onClose).toHaveBeenCalledTimes(1);
  });

  it('renders all four action buttons', () => {
    renderPanel();
    expect(screen.getByText('Summarize')).toBeInTheDocument();
    expect(screen.getByText('Critique')).toBeInTheDocument();
    expect(screen.getByText('Suggest Links')).toBeInTheDocument();
    expect(screen.getByText('Ingest')).toBeInTheDocument();
  });

  /**
   * The action result section is only rendered when `result` state is non-null.
   * It contains a header <span> whose text matches the actionLabel map:
   *   'summary' → 'Summary', 'critique' → 'Critique', etc.
   * These header labels are DISTINCT from the button labels ('Summarize',
   * 'Critique', etc.).  We assert that the result-header text 'Summary'
   * (not the button label 'Summarize') is absent initially.
   *
   * The dismiss button renders as '×' and is also absent initially.
   */
  it('does not render action result section initially', () => {
    renderPanel();
    // The result header <span> texts are 'Summary', 'Critique', 'Suggested Links', 'Ingest Status'
    // None of these match the button labels ('Summarize', 'Critique', 'Suggest Links', 'Ingest')
    // so only 'Summary', 'Suggested Links', and 'Ingest Status' are safe to query
    expect(screen.queryByText('Summary')).not.toBeInTheDocument();
    expect(screen.queryByText('Suggested Links')).not.toBeInTheDocument();
    expect(screen.queryByText('Ingest Status')).not.toBeInTheDocument();
    // The dismiss '×' button only appears when result != null
    expect(screen.queryByText('×')).not.toBeInTheDocument();
  });

  it('shows Summary result header after clicking Summarize', async () => {
    renderPanel();
    fireEvent.click(screen.getByText('Summarize'));
    await waitFor(() =>
      expect(screen.getByText('Summary')).toBeInTheDocument()
    );
  });

  it('renders word count when provided', () => {
    renderPanel();
    expect(screen.getByText('12 words')).toBeInTheDocument();
  });
});
