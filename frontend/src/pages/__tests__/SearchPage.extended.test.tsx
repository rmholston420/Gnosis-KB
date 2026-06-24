/**
 * SearchPage.extended.test.tsx
 * Targets uncovered lines:
 *   45-48 — doSearch early return when query is blank
 *   56     — setError(true) on catch
 *   121    — isError error message rendered
 *   141    — "No results found" empty state
 *   148-150 — "Showing X of Y results" footer
 */
import React from 'react';
import { render, screen, fireEvent, waitFor, act } from '@testing-library/react';
import { describe, it, expect, vi, beforeEach } from 'vitest';
import { MemoryRouter } from 'react-router-dom';

const mockSearch = vi.fn();

vi.mock('@/services/api', () => ({
  default: {
    search: (...a: unknown[]) => mockSearch(...a),
    listNotes: vi.fn().mockResolvedValue({ items: [] }),
  },
}));

const mockNavigate = vi.fn();
vi.mock('react-router-dom', async (orig) => {
  const actual = await orig<typeof import('react-router-dom')>();
  return { ...actual, useNavigate: () => mockNavigate };
});

import SearchPage from '@/pages/SearchPage';

const RESULTS = [
  { id: 's1', title: 'Dharma One', slug: 'dharma-one', note_type: 'permanent',
    tags: [], snippet: 'First result snippet', score: 0.9 },
  { id: 's2', title: 'Dharma Two', slug: 'dharma-two', note_type: 'permanent',
    tags: [], snippet: 'Second result snippet', score: 0.8 },
];

function renderPage() {
  return render(
    <MemoryRouter>
      <SearchPage />
    </MemoryRouter>
  );
}

// ─────────────────────────────────────────────────────────────────────────────
describe('SearchPage — blank query early return (lines 45-48)', () => {
  beforeEach(() => { vi.clearAllMocks(); });

  it('does not call api.search when query is blank', async () => {
    renderPage();
    const searchInput = screen.getByRole('searchbox') ?? screen.getByRole('textbox');
    fireEvent.change(searchInput, { target: { value: '' } });
    const form = searchInput.closest('form');
    if (form) fireEvent.submit(form);
    else {
      const btn = screen.queryByRole('button', { name: /search/i });
      if (btn) fireEvent.click(btn);
    }
    await act(async () => {});
    expect(mockSearch).not.toHaveBeenCalled();
  });
});

// ─────────────────────────────────────────────────────────────────────────────
describe('SearchPage — error state (line 56 + 121)', () => {
  beforeEach(() => { vi.clearAllMocks(); });

  it('shows error message when search rejects', async () => {
    mockSearch.mockRejectedValue(new Error('Search failed'));
    renderPage();
    const searchInput = screen.getByRole('searchbox') ?? screen.getByRole('textbox');
    fireEvent.change(searchInput, { target: { value: 'dharma' } });
    const form = searchInput.closest('form');
    if (form) fireEvent.submit(form);
    await waitFor(() => expect(screen.queryByText(/error|failed/i)).toBeTruthy());
  });
});

// ─────────────────────────────────────────────────────────────────────────────
describe('SearchPage — no results empty state (line 141)', () => {
  beforeEach(() => { vi.clearAllMocks(); });

  it('shows "No results" when search returns empty array', async () => {
    mockSearch.mockResolvedValue({ items: [], total: 0 });
    renderPage();
    const searchInput = screen.getByRole('searchbox') ?? screen.getByRole('textbox');
    fireEvent.change(searchInput, { target: { value: 'xyznotfound' } });
    const form = searchInput.closest('form');
    if (form) fireEvent.submit(form);
    await waitFor(() => expect(screen.queryByText(/no results/i)).toBeTruthy());
  });
});

// ─────────────────────────────────────────────────────────────────────────────
describe('SearchPage — results footer (lines 148-150)', () => {
  beforeEach(() => { vi.clearAllMocks(); });

  it('shows result count when results returned', async () => {
    mockSearch.mockResolvedValue({ items: RESULTS, total: 2 });
    renderPage();
    const searchInput = screen.getByRole('searchbox') ?? screen.getByRole('textbox');
    fireEvent.change(searchInput, { target: { value: 'dharma' } });
    const form = searchInput.closest('form');
    if (form) fireEvent.submit(form);
    await waitFor(() => expect(screen.queryByText('Dharma One')).toBeTruthy());
    expect(screen.queryByText(/showing|results/i)).toBeTruthy();
  });
});
