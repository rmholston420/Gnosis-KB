/**
 * NoteDetailPanel.test.tsx
 * ========================
 * Tests for the read-only note detail side-panel.
 *
 * We mock api.getNote so tests never hit the network, and mock
 * react-router useParams / useNavigate for controlled navigation.
 */
import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, waitFor, fireEvent } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import NoteDetailPanel from '../NoteDetailPanel';
import type { Note } from '../../types';

const mockNavigate = vi.fn();
vi.mock('react-router-dom', async () => {
  const actual = await vi.importActual<typeof import('react-router-dom')>('react-router-dom');
  return {
    ...actual,
    useNavigate: () => mockNavigate,
    useParams:   () => ({ id: 'note-abc' }),
  };
});

const mockGetNote = vi.fn();
vi.mock('../../services/api', () => ({
  api: {
    getNote:    (...args: unknown[]) => mockGetNote(...args),
    updateNote: vi.fn().mockResolvedValue({}),
    deleteNote: vi.fn().mockResolvedValue({}),
  },
}));

const baseNote: Note = {
  id:            'note-abc',
  title:         'Śūnyatā',
  slug:          'sunyata',
  body:          '## Emptiness\n\nAll phenomena lack inherent existence.',
  note_type:     'permanent',
  tags:          ['buddhism', 'madhyamaka'],
  folder:        null,
  created_at:    '2025-01-01T00:00:00Z',
  updated_at:    '2025-06-01T00:00:00Z',
  incoming_links: [],
  outgoing_links: [],
};

function renderPanel() {
  return render(<MemoryRouter><NoteDetailPanel /></MemoryRouter>);
}

beforeEach(() => {
  mockGetNote.mockReset();
  mockNavigate.mockReset();
  mockGetNote.mockResolvedValue(baseNote);
});

describe('NoteDetailPanel', () => {
  it('renders a loading state before data arrives', () => {
    // Never resolve to keep loading state visible
    mockGetNote.mockReturnValue(new Promise(() => {}));
    renderPanel();
    // Should not immediately show note content
    expect(screen.queryByText('Śūnyatā')).not.toBeInTheDocument();
  });

  it('renders note title after loading', async () => {
    renderPanel();
    await waitFor(() => expect(screen.getByText('Śūnyatā')).toBeInTheDocument());
  });

  it('renders note tags', async () => {
    renderPanel();
    await waitFor(() => {
      expect(screen.getByText('buddhism')).toBeInTheDocument();
      expect(screen.getByText('madhyamaka')).toBeInTheDocument();
    });
  });

  it('renders note_type badge', async () => {
    renderPanel();
    await waitFor(() => expect(screen.getByText('permanent')).toBeInTheDocument());
  });

  it('calls api.getNote with the id from useParams', async () => {
    renderPanel();
    await waitFor(() => expect(mockGetNote).toHaveBeenCalledWith('note-abc'));
  });

  it('shows an error state when getNote rejects', async () => {
    mockGetNote.mockRejectedValue(new Error('Network error'));
    renderPanel();
    await waitFor(() =>
      expect(screen.getByText(/error|failed|not found/i)).toBeInTheDocument()
    );
  });

  it('renders Edit button that navigates to note editor', async () => {
    renderPanel();
    await waitFor(() => screen.getByText('Śūnyatā'));
    const editBtn = screen.getByRole('button', { name: /edit/i });
    fireEvent.click(editBtn);
    expect(mockNavigate).toHaveBeenCalledWith('/notes/note-abc/edit');
  });

  it('renders markdown body content', async () => {
    renderPanel();
    await waitFor(() => screen.getByText('Śūnyatā'));
    // The rendered markdown should contain the heading text
    expect(screen.getByText(/emptiness/i)).toBeInTheDocument();
  });
});
