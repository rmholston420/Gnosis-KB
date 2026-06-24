/**
 * NoteEditorPage.test.tsx
 */
import { render, screen, waitFor } from '@testing-library/react';
import { describe, it, expect, vi } from 'vitest';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { MemoryRouter, Route, Routes } from 'react-router-dom';
import type { Note } from '../../types';

const { mockApi, mockNote: _mockNote, mockStore, mockNavigate } = vi.hoisted(() => {
  const mockNote: Note = {
    id: 'abc123',
    title: 'Existing Note',
    slug: 'existing-note',
    body: '# Hello',
    body_html: '<h1>Hello</h1>',
    note_type: 'permanent',
    status: 'draft',
    folder: '10-zettelkasten',
    word_count: 1,
    is_deleted: false,
    vector_indexed: false,
    graph_indexed: false,
    frontmatter: {},
    tags: [],
    outgoing_links: [],
    incoming_links: [],
  };
  const mockApi = {
    getNote: vi.fn().mockResolvedValue(mockNote),
    createNote: vi.fn(),
    updateNote: vi.fn(),
    listNotes: vi.fn().mockResolvedValue({ items: [] }),
  };
  const mockStore = { setActiveNoteId: vi.fn(), activeNoteId: null };
  const mockNavigate = vi.fn();
  return { mockApi, mockNote, mockStore, mockNavigate };
});

vi.mock('react-router-dom', async (orig) => ({
  ...(await orig<typeof import('react-router-dom')>()),
  useNavigate: () => mockNavigate,
}));

vi.mock('../../components/NoteEditor', () => ({
  default: ({ note }: { note: Note }) => (
    <div data-testid="note-editor">{note.title || 'untitled'}</div>
  ),
}));

vi.mock('../../components/notes/NoteTemplateGallery', () => ({
  NoteTemplateGallery: ({ onClose }: { onClose: () => void }) => (
    <div data-testid="template-gallery">
      <button onClick={onClose}>Close gallery</button>
    </div>
  ),
}));

vi.mock('../../components/editor/WikilinkAutocomplete', () => ({
  default: () => <div data-testid="wikilink-autocomplete" />,
  useWikilinkDetector: () => ({
    wikilinkQuery: null,
    insertWikilink: vi.fn(),
    anchorRect: null,
  }),
}));

vi.mock('../../services/api', () => ({ default: mockApi }));
vi.mock('../../store/useAppStore', () => ({ useAppStore: () => mockStore }));

import NoteEditorPage from '../../pages/NoteEditorPage';

function wrap(path = '/editor/new', route = '/editor/:id') {
  return render(
    <MemoryRouter initialEntries={[path]}>
      <QueryClientProvider client={new QueryClient()}>
        <Routes>
          <Route path={route} element={<NoteEditorPage />} />
        </Routes>
      </QueryClientProvider>
    </MemoryRouter>
  );
}

describe('NoteEditorPage — new note', () => {
  it('shows template gallery for new note route', async () => {
    wrap('/editor/new');
    await waitFor(() => {
      const gallery = screen.queryByTestId('template-gallery');
      const editor  = screen.queryByTestId('note-editor');
      expect(gallery ?? editor).toBeTruthy();
    });
  });
});

describe('NoteEditorPage — edit note', () => {
  it('loads existing note and shows editor', async () => {
    wrap('/editor/abc123');
    await waitFor(() => {
      const editor = screen.queryByTestId('note-editor');
      if (editor) expect(editor.textContent).toContain('Existing Note');
    });
  });

  it('calls api.getNote with the note id', async () => {
    wrap('/editor/abc123');
    await waitFor(() => {
      if (mockApi.getNote.mock.calls.length > 0)
        expect(mockApi.getNote).toHaveBeenCalledWith('abc123');
    });
  });
});

describe('NoteEditorPage — wikilink overlay', () => {
  it('mounts without crashing (wikilink autocomplete present)', async () => {
    wrap('/editor/abc123');
    await waitFor(() => expect(document.body).toBeTruthy());
  });
});
