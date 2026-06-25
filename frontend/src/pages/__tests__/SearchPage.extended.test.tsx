/**
 * SearchPage.extended.test.tsx
 * Extended coverage: blank query, error state, empty results, result count.
 *
 * SearchPage calls useSearch (a composite hook) — not useHybridSearch directly.
 * Tests spy on useSearch and fire a form submit to trigger the results branch.
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

type UseSearchReturn = ReturnType<typeof searchHooks.useSearch>;

const idle = {
  data: undefined, isLoading: false, isError: false,
  error: null,
} as unknown as UseSearchReturn;

const errorReturn = {
  data: undefined, isLoading: false, isError: true,
  error: new Error('Network error'),
} as unknown as UseSearchReturn;

const emptyReturn = {
  data: { items: [], total: 0 },
  isLoading: false, isError: false,
  error: null,
} as unknown as UseSearchReturn;

const resultReturn = {
  data: {
    items: [
      { note_id: 'r1', title: 'EEG Alpha Waves', snippet: 'Alpha waves appear...', score: 0.9, tags: [], note_type: 'permanent' },
      { note_id: 'r2', title: 'Theta Rhythm',    snippet: 'Theta occurs...',      score: 0.8, tags: [], note_type: 'permanent' },
    ],
    total: 2,
  },
  isLoading: false, isError: false,
  error: null,
} as unknown as UseSearchReturn;

function submitSearch(value: string) {
  const input = screen.getByRole('searchbox');
  fireEvent.change(input, { target: { value } });
  fireEvent.submit(input.closest('form')!);
}

afterEach((): void => { vi.restoreAllMocks(); });

describe('SearchPage — blank query early return', () => {
  it('calls the search hook with empty string on mount', () => {
    const spy = vi.spyOn(searchHooks, 'useSearch').mockReturnValue(idle);
    render(<Wrapper />);
    expect(spy).toHaveBeenCalledWith('', 'hybrid');
  });
});

describe('SearchPage — error state', () => {
  it('shows error message when hook reports isError', () => {
    vi.spyOn(searchHooks, 'useSearch').mockReturnValue(errorReturn);
    render(<Wrapper />);
    submitSearch('EEG');
    expect(screen.getByText(/search failed/i)).toBeInTheDocument();
  });
});

describe('SearchPage — no results empty state', () => {
  it('shows "No results" when hook returns empty items array', () => {
    vi.spyOn(searchHooks, 'useSearch').mockReturnValue(emptyReturn);
    render(<Wrapper />);
    submitSearch('xyz');
    expect(screen.getByText(/no results/i)).toBeInTheDocument();
  });
});

describe('SearchPage — results', () => {
  it('shows result titles and count badge when hook returns items', () => {
    vi.spyOn(searchHooks, 'useSearch').mockReturnValue(resultReturn);
    render(<Wrapper />);
    submitSearch('EEG');
    expect(screen.getByRole('heading', { name: /EEG Alpha Waves/i })).toBeInTheDocument();
    expect(screen.getByRole('heading', { name: /Theta Rhythm/i })).toBeInTheDocument();
    expect(screen.getByText(/2 results/i)).toBeInTheDocument();
  });
});
