/**
 * SearchPage.extended.test.tsx
 * Extended coverage: blank query, error state, empty results, result count.
 */
import React from 'react';
import { render, screen, fireEvent } from '@testing-library/react';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { MemoryRouter } from 'react-router-dom';
import { vi, describe, it, expect, beforeEach, afterEach } from 'vitest';
import * as searchHooks from '../../hooks/useSearch';
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

const idle = {
  data: undefined, isLoading: false, isError: false,
  error: null, status: 'success', fetchStatus: 'idle',
} as unknown as ReturnType<typeof searchHooks.useHybridSearch>;

const errorReturn = {
  data: undefined, isLoading: false, isError: true,
  error: new Error('Network error'), status: 'error', fetchStatus: 'idle',
} as unknown as ReturnType<typeof searchHooks.useHybridSearch>;

const resultReturn = {
  data: {
    items: [
      { note_id: 'r1', title: 'EEG Alpha Waves', snippet: 'Alpha waves appear...', score: 0.9, tags: [], note_type: 'permanent' },
      { note_id: 'r2', title: 'Theta Rhythm',    snippet: 'Theta occurs...',      score: 0.8, tags: [], note_type: 'permanent' },
    ],
    total: 2,
  },
  isLoading: false, isError: false,
  error: null, status: 'success', fetchStatus: 'idle',
} as unknown as ReturnType<typeof searchHooks.useHybridSearch>;

const semanticStubs = () => {
  vi.spyOn(searchHooks, 'useSemanticSearch').mockReturnValue(idle);
  vi.spyOn(searchHooks, 'useSimilarNotes').mockReturnValue(
    { data: [], isLoading: false, isError: false } as unknown as ReturnType<typeof searchHooks.useSimilarNotes>
  );
};

afterEach(() => vi.restoreAllMocks());

describe('SearchPage — blank query early return', () => {
  it('calls the search hook with empty string on mount', () => {
    const spy = vi.spyOn(searchHooks, 'useHybridSearch').mockReturnValue(idle);
    vi.spyOn(searchHooks, 'useKeywordSearch').mockReturnValue(idle);
    semanticStubs();
    render(<Wrapper />);
    expect(spy).toHaveBeenCalledWith('');
  });
});

describe('SearchPage — error state', () => {
  it('shows error message when hook reports isError', () => {
    vi.spyOn(searchHooks, 'useHybridSearch').mockReturnValue(errorReturn);
    vi.spyOn(searchHooks, 'useKeywordSearch').mockReturnValue(idle);
    semanticStubs();
    render(<Wrapper />);
    fireEvent.change(screen.getByRole('searchbox'), { target: { value: 'EEG' } });
    expect(screen.getByText(/search failed/i)).toBeInTheDocument();
  });
});

describe('SearchPage — no results empty state', () => {
  it('shows "No results" when hook returns empty items array', () => {
    vi.spyOn(searchHooks, 'useHybridSearch').mockReturnValue({
      data: { items: [], total: 0 },
      isLoading: false, isError: false,
      error: null, status: 'success', fetchStatus: 'idle',
    } as unknown as ReturnType<typeof searchHooks.useHybridSearch>);
    vi.spyOn(searchHooks, 'useKeywordSearch').mockReturnValue(idle);
    semanticStubs();
    render(<Wrapper />);
    fireEvent.change(screen.getByRole('searchbox'), { target: { value: 'xyz' } });
    expect(screen.getByText(/no results/i)).toBeInTheDocument();
  });
});

describe('SearchPage — results', () => {
  it('shows result titles and count badge when hook returns items', () => {
    vi.spyOn(searchHooks, 'useHybridSearch').mockReturnValue(resultReturn);
    vi.spyOn(searchHooks, 'useKeywordSearch').mockReturnValue(idle);
    semanticStubs();
    render(<Wrapper />);
    fireEvent.change(screen.getByRole('searchbox'), { target: { value: 'EEG' } });
    expect(screen.getByRole('heading', { name: /EEG Alpha Waves/i })).toBeInTheDocument();
    expect(screen.getByRole('heading', { name: /Theta Rhythm/i })).toBeInTheDocument();
    expect(screen.getByText(/2 results/i)).toBeInTheDocument();
  });
});
