/**
 * SearchPage.extended.test.tsx — extended tests for SearchPage.
 */
import React from 'react';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { MemoryRouter } from 'react-router-dom';
import { vi, describe, it, expect, afterEach } from 'vitest';
import SearchPage from '../SearchPage';

// SearchResults and SemanticSearch are NAMED exports — mock accordingly
vi.mock('../../components/search/SearchResults', () => ({
  SearchResults: ({ query }: { query: string }) => <div data-testid="search-results">{query}</div>,
}));
vi.mock('../../components/search/SemanticSearch', () => ({
  SemanticSearch: () => <div data-testid="semantic-search" />,
}));
vi.mock('../../hooks/useSearch', () => ({
  useSearch: vi.fn(() => ({ data: undefined, isLoading: false, isError: false })),
}));

function Wrapper({ children }: { children: React.ReactNode }) {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return (
    <QueryClientProvider client={qc}>
      <MemoryRouter>{children}</MemoryRouter>
    </QueryClientProvider>
  );
}

afterEach(() => { vi.restoreAllMocks(); });

describe('SearchPage (extended)', () => {
  it('renders the search input and mode tabs', () => {
    render(<Wrapper><SearchPage /></Wrapper>);
    expect(screen.getByPlaceholderText(/search your vault/i)).toBeInTheDocument();
    // Tabs have role="tab"
    expect(screen.getByRole('tab', { name: /hybrid/i })).toBeInTheDocument();
    expect(screen.getByRole('tab', { name: /semantic/i })).toBeInTheDocument();
  });

  it('shows SemanticSearch panel when mode is semantic', async () => {
    render(<Wrapper><SearchPage /></Wrapper>);
    // Switch to semantic mode via the tab
    fireEvent.click(screen.getByRole('tab', { name: /semantic/i }));
    await waitFor(() =>
      expect(screen.getByTestId('semantic-search')).toBeInTheDocument()
    );
  });
});
