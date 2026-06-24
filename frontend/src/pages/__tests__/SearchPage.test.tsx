/**
 * SearchPage.test.tsx
 * Tests:
 *  - renders search input and three mode tabs
 *  - switching to Semantic tab renders SemanticSearch
 *  - switching to Keyword tab uses keyword results branch
 *  - initial ?q= param pre-fills the input
 */
import React from 'react';
import { render, screen, fireEvent } from '@testing-library/react';
import { MemoryRouter, Routes, Route } from 'react-router-dom';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
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

beforeEach(() => {
  vi.spyOn(searchHooks, 'useHybridSearch').mockReturnValue({
    data: { items: [], total: 0 }, isLoading: false, isError: false,
  } as ReturnType<typeof searchHooks.useHybridSearch>);
  vi.spyOn(searchHooks, 'useKeywordSearch').mockReturnValue({
    data: { items: [], total: 0 }, isLoading: false, isError: false,
  } as ReturnType<typeof searchHooks.useKeywordSearch>);
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
    // SemanticSearch has a distinctive aria label or test id
    expect(screen.getByTestId('semantic-search')).toBeInTheDocument();
  });
});
