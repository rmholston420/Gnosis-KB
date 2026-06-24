/**
 * SearchPage.extended.test.tsx
 * Extended coverage: blank query, error state, empty results, result count.
 * Wraps with QueryClientProvider so useHybridSearch (useQuery) works.
 */
import React from 'react';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { MemoryRouter } from 'react-router-dom';
import { vi, describe, it, expect, beforeEach } from 'vitest';
import * as searchApi from '../../api/search';
import SearchPage from '../SearchPage';

function Wrapper() {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return (
    <QueryClientProvider client={qc}>
      <MemoryRouter>
        <SearchPage />
      </MemoryRouter>
    </QueryClientProvider>
  );
}

const resultFixture = {
  results: [
    { note_id: 'r1', title: 'EEG Alpha Waves', snippet: 'Alpha waves appear...', score: 0.9, tags: [], note_type: 'permanent' },
    { note_id: 'r2', title: 'Theta Rhythm', snippet: 'Theta occurs...', score: 0.8, tags: [], note_type: 'permanent' },
  ],
  total: 2,
  query: 'EEG',
  mode: 'hybrid' as const,
};

describe('SearchPage — blank query early return (lines 45-48)', () => {
  it('does not call api.search when query is blank', async () => {
    const spy = vi.spyOn(searchApi, 'search').mockResolvedValue({ results: [], total: 0, query: '', mode: 'hybrid' });
    render(<Wrapper />);
    // No query typed — search should not be called with empty string
    await new Promise((r) => setTimeout(r, 100));
    expect(spy).not.toHaveBeenCalledWith(expect.objectContaining({ q: '' }));
  });
});

describe('SearchPage — error state (line 56 + 121)', () => {
  it('shows error message when search rejects', async () => {
    vi.spyOn(searchApi, 'search').mockRejectedValue(new Error('Network error'));
    render(<Wrapper />);
    const input = screen.getByRole('searchbox');
    fireEvent.change(input, { target: { value: 'EEG' } });
    await waitFor(() => screen.getByText(/error/i), { timeout: 3000 });
    expect(screen.getByText(/error/i)).toBeInTheDocument();
  });
});

describe('SearchPage — no results empty state (line 141)', () => {
  it('shows "No results" when search returns empty array', async () => {
    vi.spyOn(searchApi, 'search').mockResolvedValue({ results: [], total: 0, query: 'xyz', mode: 'hybrid' });
    render(<Wrapper />);
    const input = screen.getByRole('searchbox');
    fireEvent.change(input, { target: { value: 'xyz' } });
    await waitFor(() => screen.getByText(/no results/i), { timeout: 3000 });
    expect(screen.getByText(/no results/i)).toBeInTheDocument();
  });
});

describe('SearchPage — results footer (lines 148-150)', () => {
  it('shows result count when results returned', async () => {
    vi.spyOn(searchApi, 'search').mockResolvedValue(resultFixture);
    render(<Wrapper />);
    const input = screen.getByRole('searchbox');
    fireEvent.change(input, { target: { value: 'EEG' } });
    await waitFor(() => screen.getByText(/EEG Alpha Waves/i), { timeout: 3000 });
    expect(screen.getByText(/2/)).toBeInTheDocument();
  });
});
