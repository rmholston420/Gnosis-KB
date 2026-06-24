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

// use getByLabelText — robust regardless of ARIA role mapping
const getInput = () => screen.getByLabelText('Search query');

// ─────────────────────────────────────────────────────────────────────────────
describe('SearchPage — blank query early return (lines 45-48)', () => {
  beforeEach(() => { vi.clearAllMocks(); mockSearch.mockResolvedValue({ items: [], total: 0 }); });

  it('does not call api.search when query is blank', async () => {
    renderPage();
    fireEvent.change(getInput(), { target: { value: '' } });
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
    fireEvent.change(getInput(), { target: { value: 'dharma' } });
    await waitFor(() => expect(screen.queryByText(/error|failed/i)).toBeTruthy());
  });
});

// ─────────────────────────────────────────────────────────────────────────────
describe('SearchPage — no results empty state (line 141)', () => {
  beforeEach(() => { vi.clearAllMocks(); });

  it('shows "No results" when search returns empty array', async () => {
    mockSearch.mockResolvedValue({ items: [], total: 0 });
    renderPage();
    fireEvent.change(getInput(), { target: { value: 'xyznotfound' } });
    await waitFor(() => expect(screen.queryByText(/no results/i)).toBeTruthy());
  });
});

// ─────────────────────────────────────────────────────────────────────────────
describe('SearchPage — results footer (lines 148-150)', () => {
  beforeEach(() => { vi.clearAllMocks(); });

  it('shows result count when results returned', async () => {
    mockSearch.mockResolvedValue({ items: RESULTS, total: 2 });
    renderPage();
    fireEvent.change(getInput(), { target: { value: 'dharma' } });
    await waitFor(() => expect(screen.queryByText('Dharma One')).toBeTruthy());
    expect(screen.queryByText(/result/i)).toBeTruthy();
  });
});
