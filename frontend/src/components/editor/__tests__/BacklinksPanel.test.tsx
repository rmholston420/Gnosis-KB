/**
 * BacklinksPanel.test.tsx — tests for the editor BacklinksPanel.
 */
import React from 'react';
import { render, screen } from '@testing-library/react';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { BacklinksPanel } from '../BacklinksPanel';

const wrapper = ({ children }: { children: React.ReactNode }) => (
  <QueryClientProvider client={new QueryClient({ defaultOptions: { queries: { retry: false } } })}>
    {children}
  </QueryClientProvider>
);

describe('BacklinksPanel (editor)', () => {
  it('renders empty state when noteId is null', () => {
    // BacklinksPanel now accepts string | null | undefined
    render(<BacklinksPanel noteId={null} />, { wrapper });
    expect(screen.getByText(/no note selected/i)).toBeInTheDocument();
  });

  it('renders loading state with a valid noteId', () => {
    render(<BacklinksPanel noteId="note-1" />, { wrapper });
    expect(screen.getByText(/loading/i)).toBeInTheDocument();
  });
});
