/**
 * SearchPage.extended.test.tsx
 * Extended coverage: blank query, error state, empty results, result count.
 *
 * Strategy: spy on the HOOK layer (hooks/useSearch) not the raw api module.
 * SearchPage consumes useHybridSearch which is a useQuery wrapper; spying on
 * the hook directly is the correct interception point and avoids QueryClient
 * async plumbing for synchronous state assertions.
 */
import React from 'react';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
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

// Stub semantic hooks used when SemanticSearch mounts (mode stays hybrid here)
const semanticStubs = () => {
  vi.spyOn(searchHooks, 'useSemanticSearch').mockReturnValue(idle);
  vi.spyOn(searchHooks, 'useSimilarNotes').mockReturnValue(
    { data: [], isLoading: false, isError: false } as unknown as ReturnType<typeof searchHooks.useSimilarNotes>
  );
};

afterEach(() => vi.restoreAllMocks());

describe('SearchPage — blank query early return (lines 45-48)', () => {
  it('does not call the search hook with a non-empty query when blank', () => {
    const spy = vi.spyOn(searchHooks, 'useHybridSearch').mockReturnValue(idle);
    vi.spyOn(searchHooks, 'useKeywordSearch').mockReturnValue(idle);
    semanticStubs();
    render(<Wrapper />);
    // Input is blank on mount — hook is called with empty string
    expect(spy).toHaveBeenCalledWith('');
  });
});

describe('SearchPage — error state (line 56 + 121)', () => {
  it('shows error message when hook reports isError', () => {
    vi.spyOn(searchHooks, 'useHybridSearch').mockReturnValue(errorReturn);
    vi.spyOn(searchHooks, 'useKeywordSearch').mockReturnValue(idle);
    semanticStubs();
    render(<Wrapper />);
    const input = screen.getByRole('searchbox');
    fireEvent.change(input, { target: { value: 'EEG' } });
    // isError is true synchronously — no waitFor needed
    expect(screen.getByText(/search failed/i)).toBeInTheDocument();
  });
});

describe('SearchPage — no results empty state (line 141)', () => {
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

describe('SearchPage — results footer (lines 148-150)', () => {
  it('shows result titles when hook returns items', () => {
    vi.spyOn(searchHooks, 'useHybridSearch').mockReturnValue(resultReturn);
    vi.spyOn(searchHooks, 'useKeywordSearch').mockReturnValue(idle);
    semanticStubs();
    render(<Wrapper />);
    fireEvent.change(screen.getByRole('searchbox'), { target: { value: 'EEG' } });
    // Title may be split by <Highlight> — use heading role matcher
    expect(screen.getByRole('heading', { name: /EEG Alpha Waves/i })).toBeInTheDocument();
    expect(screen.getByRole('heading', { name: /Theta Rhythm/i })).toBeInTheDocument();
    // Total count badge
    expect(screen.getByText(/2 results/i)).toBeInTheDocument();
  });
});
