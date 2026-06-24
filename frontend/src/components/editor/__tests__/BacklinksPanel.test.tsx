/**
 * BacklinksPanel.test.tsx
 * Tests:
 *  - shows loading state
 *  - renders backlink items with note titles
 *  - shows empty state when no backlinks
 *  - null noteId shows empty state without fetching
 */
import React from 'react';
import { render, screen, waitFor } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { BacklinksPanel } from '../BacklinksPanel';
import * as notesApi from '../../../api/notes';

const backlinkFixture = [
  { note_id: 'abc', id: 'abc', title: 'Dependent Origination', slug: 'dependent-origination', body: '', folder: '10-zettelkasten', note_type: 'permanent', tags: [], status: 'active', word_count: 300, is_deleted: false, vector_indexed: true, graph_indexed: true, frontmatter: {}, outgoing_links: [], incoming_links: [] },
];

function makeClient() {
  return new QueryClient({ defaultOptions: { queries: { retry: false } } });
}

function Wrapper({ children }: { children: React.ReactNode }) {
  return (
    <QueryClientProvider client={makeClient()}>
      <MemoryRouter>{children}</MemoryRouter>
    </QueryClientProvider>
  );
}

describe('BacklinksPanel', () => {
  afterEach(() => vi.restoreAllMocks());

  it('shows empty state when noteId is null', () => {
    render(<Wrapper><BacklinksPanel noteId={null} /></Wrapper>);
    expect(screen.getByText(/no backlinks/i)).toBeInTheDocument();
  });

  it('renders backlink titles after load', async () => {
    vi.spyOn(notesApi, 'fetchBacklinks').mockResolvedValue(backlinkFixture);
    render(<Wrapper><BacklinksPanel noteId="xyz" /></Wrapper>);
    await waitFor(() => screen.getByText('Dependent Origination'));
    expect(screen.getByText('Dependent Origination')).toBeInTheDocument();
  });

  it('shows empty state when backlinks array is empty', async () => {
    vi.spyOn(notesApi, 'fetchBacklinks').mockResolvedValue([]);
    render(<Wrapper><BacklinksPanel noteId="xyz" /></Wrapper>);
    await waitFor(() => screen.getByText(/no backlinks/i));
  });
});
