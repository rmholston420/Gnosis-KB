import { describe, it, expect, vi } from 'vitest';
import { render, screen, fireEvent } from '@testing-library/react';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { MemoryRouter } from 'react-router-dom';
import { createElement } from 'react';
import SearchPage from '../SearchPage';

vi.mock('../../hooks/useSearch', () => ({
  useSearch: vi.fn(() => ({ data: undefined, isLoading: false, isError: false })),
}));
// SearchResults and SemanticSearch are NAMED exports — mock accordingly
vi.mock('../../components/search/SearchResults', () => ({
  SearchResults: ({ query }: { query: string }) => <div data-testid="search-results">{query}</div>,
}));
vi.mock('../../components/search/SemanticSearch', () => ({
  SemanticSearch: () => <div data-testid="semantic-search" />,
}));

function wrap(ui: React.ReactNode) {
  const qc = new QueryClient();
  return render(
    createElement(QueryClientProvider, { client: qc },
      createElement(MemoryRouter, null, ui)
    )
  );
}

describe('SearchPage', () => {
  it('renders mode tabs', () => {
    wrap(<SearchPage />);
    expect(screen.getByRole('tab', { name: /hybrid/i })).toBeInTheDocument();
    expect(screen.getByRole('tab', { name: /semantic/i })).toBeInTheDocument();
    expect(screen.getByRole('tab', { name: /keyword/i })).toBeInTheDocument();
  });

  it('shows search input for non-semantic mode', () => {
    wrap(<SearchPage />);
    expect(screen.getByRole('searchbox')).toBeInTheDocument();
  });

  it('switches to semantic component when Semantic tab clicked', () => {
    wrap(<SearchPage />);
    fireEvent.click(screen.getByRole('tab', { name: /semantic/i }));
    expect(screen.getByTestId('semantic-search')).toBeInTheDocument();
    expect(screen.queryByRole('searchbox')).not.toBeInTheDocument();
  });

  it('submitting form updates query', () => {
    wrap(<SearchPage />);
    const input = screen.getByRole('searchbox');
    fireEvent.change(input, { target: { value: 'zettelkasten' } });
    fireEvent.submit(input.closest('form')!);
    // SearchResults is rendered with the submitted query
    expect(screen.getByTestId('search-results').textContent).toBe('zettelkasten');
  });
});
