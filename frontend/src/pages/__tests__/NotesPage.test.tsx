/**
 * NotesPage.test.tsx
 * ==================
 * Integration-light test for the main Notes list page.
 */
import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, waitFor } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import NotesPage from '../NotesPage';
import { useAppStore } from '../../store/useAppStore';

const mockNavigate = vi.fn();
vi.mock('react-router-dom', async () => {
  const actual = await vi.importActual<typeof import('react-router-dom')>('react-router-dom');
  return { ...actual, useNavigate: () => mockNavigate };
});

const mockListNotes = vi.fn();
vi.mock('../../services/api', () => ({
  default: {
    listNotes:  (...args: unknown[]) => mockListNotes(...args),
    deleteNote: vi.fn().mockResolvedValue({}),
  },
}));

const notes = [
  { id: 'n1', title: 'Emptiness', slug: 'emptiness', note_type: 'permanent', tags: [], updated_at: '2025-01-01T00:00:00Z', word_count: 10, folder: null },
  { id: 'n2', title: 'Impermanence', slug: 'impermanence', note_type: 'fleeting', tags: ['core'], updated_at: '2025-01-02T00:00:00Z', word_count: 5, folder: null },
];

function renderPage() {
  return render(<MemoryRouter><NotesPage /></MemoryRouter>);
}

beforeEach(() => {
  mockListNotes.mockReset();
  mockNavigate.mockReset();
  useAppStore.setState({ activeFolder: null, searchQuery: '' });
  mockListNotes.mockResolvedValue({ items: notes, total: 2 });
});

describe('NotesPage', () => {
  it('renders without crashing', () => {
    renderPage();
    expect(document.body).toBeInTheDocument();
  });

  it('renders note titles after loading', async () => {
    renderPage();
    await waitFor(() => expect(screen.getByText('Emptiness')).toBeInTheDocument());
    expect(screen.getByText('Impermanence')).toBeInTheDocument();
  });

  it('calls listNotes on mount', async () => {
    renderPage();
    await waitFor(() => expect(mockListNotes).toHaveBeenCalled());
  });

  it('renders empty state when no notes', async () => {
    mockListNotes.mockResolvedValue({ items: [], total: 0 });
    renderPage();
    await waitFor(() =>
      expect(screen.getByText(/no notes|empty|create/i)).toBeInTheDocument()
    );
  });
});
