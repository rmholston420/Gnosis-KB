/**
 * SearchPage.extended.test.tsx — extended tests for SearchPage.
 */
import React from 'react';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { MemoryRouter } from 'react-router-dom';
import { vi, describe, it, expect, afterEach } from 'vitest';
import SearchPage from '../SearchPage';

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
    expect(screen.getByRole('button', { name: /hybrid/i })).toBeInTheDocument();
    expect(screen.getByRole('button', { name: /semantic/i })).toBeInTheDocument();
  });

  it('shows SemanticSearch panel when mode is semantic and query is submitted', async () => {
    render(<Wrapper><SearchPage /></Wrapper>);
    // Switch to semantic mode
    fireEvent.click(screen.getByRole('button', { name: /semantic/i }));
    // Type a query and submit
    const input = screen.getByPlaceholderText(/search your vault/i);
    fireEvent.change(input, { target: { value: 'emptiness' } });
    fireEvent.submit(input.closest('form')!);
    await waitFor(() =>
      expect(screen.getByTestId('semantic-search')).toBeInTheDocument()
    );
  });
});
