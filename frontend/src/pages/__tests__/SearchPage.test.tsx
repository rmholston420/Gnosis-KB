/**
 * SearchPage.test.tsx
 * Tests:
 *  - renders search input and three mode tabs
 *  - switching to Semantic tab renders SemanticSearch (data-testid="semantic-search")
 *  - initial ?q= param pre-fills the input
 *
 * Spy on hooks/useSearch (not the raw api module) so the mock reaches
 * the component without needing a real network or QueryClient plumbing.
 */
import React from 'react';
import { render, screen, fireEvent } from '@testing-library/react';
import { MemoryRouter, Routes, Route } from 'react-router-dom';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { vi, describe, it, expect, beforeEach, afterEach } from 'vitest';
import SearchPage from '../SearchPage';
import * as searchHooks from '../../hooks/useSearch';

function makeClient() {
  return new QueryClient({ defaultOptions: { queries: { retry: false } } });
}

function Wrapper({ initialUrl = '/search' }: { initialUrl?: string }) {
  return (
    <QueryClientProvider client={makeClient()}>
      <MemoryRouter initialEntries={[initialUrl]}>
        <Routes>
          <Route path="search" element={<SearchPage />} />
        </Routes>
      </MemoryRouter>
    </QueryClientProvider>
  );
}

const emptyHookReturn = {
  data: undefined,
  isLoading: false,
  isError: false,
  error: null,
  status: 'success' as const,
  fetchStatus: 'idle' as const,
} as unknown as ReturnType<typeof searchHooks.useHybridSearch>;

beforeEach(() => {
  vi.spyOn(searchHooks, 'useHybridSearch').mockReturnValue(emptyHookReturn);
  vi.spyOn(searchHooks, 'useKeywordSearch').mockReturnValue(emptyHookReturn);
  // SemanticSearch uses useSemanticSearch + useSimilarNotes — stub both
  vi.spyOn(searchHooks, 'useSemanticSearch').mockReturnValue(emptyHookReturn);
  vi.spyOn(searchHooks, 'useSimilarNotes').mockReturnValue({
    data: [],
    isLoading: false,
    isError: false,
  } as unknown as ReturnType<typeof searchHooks.useSimilarNotes>);
});

afterEach(() => vi.restoreAllMocks());

describe('SearchPage', () => {
  it('renders search input and three mode tabs', () => {
    render(<Wrapper />);
    expect(screen.getByRole('searchbox')).toBeInTheDocument();
    expect(screen.getByRole('button', { name: /hybrid/i })).toBeInTheDocument();
    expect(screen.getByRole('button', { name: /semantic/i })).toBeInTheDocument();
    expect(screen.getByRole('button', { name: /keyword/i })).toBeInTheDocument();
  });

  it('pre-fills input from ?q= URL param', () => {
    render(<Wrapper initialUrl="/search?q=consciousness" />);
    expect(screen.getByRole('searchbox')).toHaveValue('consciousness');
  });

  it('switching to Semantic tab renders SemanticSearch component', () => {
    render(<Wrapper />);
    fireEvent.click(screen.getByRole('button', { name: /semantic/i }));
    // SemanticSearch root has data-testid="semantic-search"
    expect(screen.getByTestId('semantic-search')).toBeInTheDocument();
  });
});
