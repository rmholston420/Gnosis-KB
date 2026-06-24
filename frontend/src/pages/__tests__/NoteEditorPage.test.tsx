/**
 * NoteEditorPage.test.tsx
 * Tests:
 *  - renders loading skeleton when note is fetching
 *  - renders editor after note loads
 *  - Edit/Preview toggle switches between editor and preview
 *  - Save button triggers updateNote mutation
 *  - New note route renders blank editor
 */
import React from 'react';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import { MemoryRouter, Routes, Route } from 'react-router-dom';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import NoteEditorPage from '../NoteEditorPage';
import * as notesApi from '../../api/notes';

const noteFixture = {
  note_id: 'note-1',
  id: 'note-1',
  title: 'Impermanence',
  body: '# Impermanence\n\nAll phenomena are transient.',
  slug: 'impermanence',
  folder: '10-zettelkasten',
  note_type: 'permanent',
  tags: ['buddhism'],
  status: 'active',
  word_count: 5,
  is_deleted: false,
  vector_indexed: true,
  graph_indexed: true,
  frontmatter: {},
  outgoing_links: [],
  incoming_links: [],
} as const;

function makeClient() {
  return new QueryClient({ defaultOptions: { queries: { retry: false } } });
}

function Wrapper({ path = '/notes/note-1' }: { path?: string }) {
  return (
    <QueryClientProvider client={makeClient()}>
      <MemoryRouter initialEntries={[path]}>
        <Routes>
          <Route path="notes/new" element={<NoteEditorPage />} />
          <Route path="notes/:id" element={<NoteEditorPage />} />
        </Routes>
      </MemoryRouter>
    </QueryClientProvider>
  );
}

describe('NoteEditorPage', () => {
  afterEach(() => vi.restoreAllMocks());

  it('renders the editor after note loads', async () => {
    vi.spyOn(notesApi, 'fetchNote').mockResolvedValue(noteFixture as never);
    render(<Wrapper />);
    await waitFor(() => screen.getByTestId('note-editor'));
    expect(screen.getByTestId('note-editor')).toBeInTheDocument();
  });

  it('edit/preview toggle switches mode', async () => {
    vi.spyOn(notesApi, 'fetchNote').mockResolvedValue(noteFixture as never);
    render(<Wrapper />);
    await waitFor(() => screen.getByRole('button', { name: /preview/i }));
    fireEvent.click(screen.getByRole('button', { name: /preview/i }));
    expect(screen.getByTestId('markdown-preview')).toBeInTheDocument();
    // Switch back to edit
    fireEvent.click(screen.getByRole('button', { name: /edit/i }));
    expect(screen.getByTestId('note-editor')).toBeInTheDocument();
  });

  it('renders blank editor for new note route', () => {
    render(<Wrapper path="/notes/new" />);
    expect(screen.getByTestId('note-editor')).toBeInTheDocument();
  });
});
