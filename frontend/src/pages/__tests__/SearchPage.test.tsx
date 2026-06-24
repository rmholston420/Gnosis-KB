/**
 * SearchPage.test.tsx
 * ===================
 */
import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import { MemoryRouter, Route, Routes } from 'react-router-dom';
import SearchPage from '../SearchPage';

const mockNavigate = vi.fn();
vi.mock('react-router-dom', async () => {
  const actual = await vi.importActual<typeof import('react-router-dom')>('react-router-dom');
  return { ...actual, useNavigate: () => mockNavigate };
});

const mockSearchNotes = vi.fn();
vi.mock('../../services/api', () => ({
  default: { searchNotes: (...args: unknown[]) => mockSearchNotes(...args) },
}));

function renderPage(initialSearch = '') {
  return render(
    <MemoryRouter initialEntries={[`/search${initialSearch}`]}>
      <Routes>
        <Route path="/search" element={<SearchPage />} />
      </Routes>
    </MemoryRouter>
  );
}

beforeEach(() => {
  mockSearchNotes.mockReset();
  mockNavigate.mockReset();
  mockSearchNotes.mockResolvedValue({ items: [], total: 0 });
});

describe('SearchPage', () => {
  it('renders the search input', () => {
    renderPage();
    expect(screen.getByRole('textbox')).toBeInTheDocument();
  });

  it('populates input from URL query param ?q=', () => {
    mockSearchNotes.mockResolvedValue({
      items: [{ id: 'n1', title: 'Karma', slug: 'karma', note_type: 'permanent', tags: [] }],
      total: 1,
    });
    renderPage('?q=karma');
    const input = screen.getByRole('textbox') as HTMLInputElement;
    expect(input.value).toBe('karma');
  });

  it('calls searchNotes when URL has ?q=', async () => {
    renderPage('?q=dharma');
    await waitFor(() => expect(mockSearchNotes).toHaveBeenCalled());
  });

  it('renders result titles', async () => {
    mockSearchNotes.mockResolvedValue({
      items: [{ id: 'n1', title: 'Karma', slug: 'karma', note_type: 'permanent', tags: [] }],
      total: 1,
    });
    renderPage('?q=karma');
    await waitFor(() => expect(screen.getByText('Karma')).toBeInTheDocument());
  });

  it('renders empty state for no results', async () => {
    renderPage('?q=xyz123');
    await waitFor(() =>
      expect(screen.getByText(/no results|not found|empty/i)).toBeInTheDocument()
    );
  });

  it('typing in the input triggers a new search', async () => {
    renderPage();
    fireEvent.change(screen.getByRole('textbox'), { target: { value: 'samsara' } });
    await waitFor(() => expect(mockSearchNotes).toHaveBeenCalled());
  });
});
