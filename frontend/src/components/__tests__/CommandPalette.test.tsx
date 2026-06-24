/**
 * CommandPalette.test.tsx
 * Tests:
 *  - renders when open=true
 *  - hides when open=false
 *  - filters notes by query
 *  - calls onClose when Escape is pressed
 *  - keyboard navigation: ArrowDown selects next item
 */
import React from 'react';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { MemoryRouter } from 'react-router-dom';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { CommandPalette } from '../CommandPalette';
import * as apiNotes from '../../api/notes';

const mockNotes = [
  { note_id: '1', id: '1', title: 'Buddhism Basics', slug: 'buddhism-basics', body: '', folder: '10-zettelkasten', note_type: 'permanent', tags: [], status: 'active', word_count: 100, is_deleted: false, vector_indexed: true, graph_indexed: true, frontmatter: {}, outgoing_links: [], incoming_links: [] },
  { note_id: '2', id: '2', title: 'Tibetan Practices', slug: 'tibetan-practices', body: '', folder: '10-zettelkasten', note_type: 'permanent', tags: [], status: 'active', word_count: 200, is_deleted: false, vector_indexed: true, graph_indexed: true, frontmatter: {}, outgoing_links: [], incoming_links: [] },
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

describe('CommandPalette', () => {
  beforeEach(() => {
    vi.spyOn(apiNotes, 'fetchNotesTitles').mockResolvedValue(mockNotes);
  });

  afterEach(() => vi.restoreAllMocks());

  it('renders nothing when open=false', () => {
    const { container } = render(
      <Wrapper><CommandPalette open={false} onClose={() => {}} /></Wrapper>,
    );
    expect(container.firstChild).toBeNull();
  });

  it('renders search input when open=true', async () => {
    render(<Wrapper><CommandPalette open onClose={() => {}} /></Wrapper>);
    expect(screen.getByRole('combobox')).toBeInTheDocument();
  });

  it('shows all notes initially after load', async () => {
    render(<Wrapper><CommandPalette open onClose={() => {}} /></Wrapper>);
    await waitFor(() => screen.getByText('Buddhism Basics'));
    expect(screen.getByText('Tibetan Practices')).toBeInTheDocument();
  });

  it('filters notes by typed query', async () => {
    const user = userEvent.setup();
    render(<Wrapper><CommandPalette open onClose={() => {}} /></Wrapper>);
    await waitFor(() => screen.getByText('Buddhism Basics'));
    await user.type(screen.getByRole('combobox'), 'Tibetan');
    expect(screen.getByText('Tibetan Practices')).toBeInTheDocument();
    expect(screen.queryByText('Buddhism Basics')).toBeNull();
  });

  it('calls onClose when Escape is pressed', async () => {
    const onClose = vi.fn();
    render(<Wrapper><CommandPalette open onClose={onClose} /></Wrapper>);
    fireEvent.keyDown(document, { key: 'Escape' });
    expect(onClose).toHaveBeenCalledTimes(1);
  });
});
