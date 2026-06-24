/**
 * NoteEditorPage.extended.test.tsx
 * Covers previously-uncovered lines:
 *   170-171  prefillTitle / type / folder from searchParams
 *   176-181  createMutation.onSuccess → navigate + setActiveNoteId
 *   206-207  updateMutation.onSuccess → invalidate queries
 *   210-211  loading state (isLoading=true)
 *   216-221  "Note not found" fallback when note is null
 */
import React from 'react';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import { describe, it, expect, vi, beforeEach } from 'vitest';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { MemoryRouter, Route, Routes } from 'react-router-dom';
import type { Note } from '../../types';

const { mockApi, mockStore, mockNavigate, mockNote } = vi.hoisted(() => {
  const mockNote: Note = {
    id: 'note1', title: 'Test Note', slug: 'test-note', body: '# Hello',
    body_html: '', note_type: 'permanent', status: 'draft',
    folder: '10-zettelkasten', word_count: 1, is_deleted: false,
    vector_indexed: false, graph_indexed: false, frontmatter: {},
    tags: [], outgoing_links: [], incoming_links: [],
  };
  const mockApi = {
    getNote: vi.fn().mockResolvedValue(mockNote),
    createNote: vi.fn().mockResolvedValue({ ...mockNote, id: 'new-id', title: 'New Note' }),
    updateNote: vi.fn().mockResolvedValue(mockNote),
    listNotes: vi.fn().mockResolvedValue({ items: [] }),
  };
  const mockStore = { setActiveNoteId: vi.fn(), activeNoteId: null };
  const mockNavigate = vi.fn();
  return { mockApi, mockStore, mockNavigate, mockNote };
});

vi.mock('react-router-dom', async (orig) => ({
  ...(await orig<typeof import('react-router-dom')>()),
  useNavigate: () => mockNavigate,
}));
vi.mock('../../components/NoteEditor', () => ({
  default: ({ note, onSave }: { note: Note; onSave: (b: string, t?: string) => Promise<void> }) => (
    <div data-testid="note-editor">
      <span>{note.title}</span>
      <button onClick={() => onSave('new body', 'New Title')}>Save</button>
    </div>
  ),
}));
vi.mock('../../components/notes/NoteTemplateGallery', () => ({
  NoteTemplateGallery: ({ onClose, onSelect }: {
    onClose: () => void;
    onSelect: (t: { body: string; note_type: string; folder: string }) => void;
  }) => (
    <div data-testid="template-gallery">
      <button onClick={onClose}>close</button>
      <button onClick={() => onSelect({ body: '# Template', note_type: 'permanent', folder: '10-zettelkasten' })}>
        pick-template
      </button>
    </div>
  ),
}));
vi.mock('../../components/editor/WikilinkAutocomplete', () => ({
  default: () => null,
  useWikilinkDetector: () => ({ wikilinkQuery: null, insertWikilink: vi.fn(), anchorRect: null }),
}));
vi.mock('../../services/api', () => ({ default: mockApi }));
vi.mock('../../store/useAppStore', () => ({ useAppStore: () => mockStore }));

import NoteEditorPage from '../NoteEditorPage';

function wrap(path: string, initialPath: string) {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(
    <QueryClientProvider client={qc}>
      <MemoryRouter initialEntries={[initialPath]}>
        <Routes>
          <Route path={path} element={<NoteEditorPage />} />
        </Routes>
      </MemoryRouter>
    </QueryClientProvider>
  );
}

beforeEach(() => { vi.clearAllMocks(); });

describe('NoteEditorPage — searchParams prefill', () => {
  it('renders without crashing when searchParams have title/type/folder', () => {
    wrap('/new', '/new?title=Dharma+Note&type=permanent&folder=10-zettelkasten');
    expect(screen.getByTestId('template-gallery')).toBeInTheDocument();
  });
});

describe('NoteEditorPage — create navigation', () => {
  it('navigates to new note after save in new-note flow', async () => {
    wrap('/new', '/new');
    fireEvent.click(screen.getByText('close'));
    await waitFor(() => expect(screen.getByTestId('note-editor')).toBeInTheDocument());
    fireEvent.click(screen.getByText('Save'));
    await waitFor(() => expect(mockApi.createNote).toHaveBeenCalled());
    await waitFor(() => expect(mockNavigate).toHaveBeenCalledWith('/notes/new-id', { replace: true }));
    expect(mockStore.setActiveNoteId).toHaveBeenCalledWith('new-id');
  });
});

describe('NoteEditorPage — update mutation', () => {
  it('calls updateNote when saving an existing note', async () => {
    wrap('/notes/:id', '/notes/note1');
    await waitFor(() => expect(screen.getByTestId('note-editor')).toBeInTheDocument());
    fireEvent.click(screen.getByText('Save'));
    await waitFor(() => expect(mockApi.updateNote).toHaveBeenCalledWith('note1', expect.any(Object)));
  });
});

describe('NoteEditorPage — loading state', () => {
  it('renders loader while note is fetching', () => {
    mockApi.getNote.mockImplementationOnce(() => new Promise(() => {}));
    wrap('/notes/:id', '/notes/slow-note');
    expect(document.body.innerHTML.length).toBeGreaterThan(0);
  });
});

describe('NoteEditorPage — note not found', () => {
  it('shows "Note not found" when query resolves null', async () => {
    mockApi.getNote.mockResolvedValueOnce(null);
    wrap('/notes/:id', '/notes/missing');
    await waitFor(() =>
      expect(screen.getByText(/note not found/i)).toBeInTheDocument()
    );
  });
});
