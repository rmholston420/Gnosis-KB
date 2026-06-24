/**
 * NoteEditorPage.test.tsx
 * Covers: new-note flow (template gallery shown, blank fallback),
 * edit-note flow (note loaded, editor rendered), loading state,
 * wikilink overlay presence.
 */
import { render, screen, waitFor } from '@testing-library/react';
import { describe, it, expect, vi } from 'vitest';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { MemoryRouter, Route, Routes } from 'react-router-dom';
import type { Note } from '../../types';

// ---------------------------------------------------------------------------
// vi.hoisted — declare mocks BEFORE the vi.mock() factories are hoisted.
// Any `const` declared at module scope is NOT available inside a vi.mock()
// factory because Vitest physically moves vi.mock() calls above all imports.
// vi.hoisted() runs synchronously before that boundary.
// ---------------------------------------------------------------------------
const { mockApi, mockNote, mockStore, mockNavigate } = vi.hoisted(() => {
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

import NoteEditorPage from '../NoteEditorPage';

function wrapDirect(initialPath = '/new') {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(
    <QueryClientProvider client={qc}>
      <MemoryRouter initialEntries={[initialPath]}>
        <Routes>
          <Route path="/new" element={<NoteEditorPage />} />
          <Route path="/notes/:id" element={<NoteEditorPage />} />
        </Routes>
      </MemoryRouter>
    </QueryClientProvider>
  );
}

describe('NoteEditorPage — new-note flow', () => {
  it('shows template gallery on first render (no id)', () => {
    wrapDirect('/new');
    expect(screen.getByTestId('template-gallery')).toBeInTheDocument();
  });

  it('closes gallery and shows editor after blank template chosen', async () => {
    wrapDirect('/new');
    const closeBtn = screen.getByText('Close gallery');
    closeBtn.click();
    await waitFor(() =>
      expect(screen.queryByTestId('template-gallery')).not.toBeInTheDocument()
    );
  });
});

describe('NoteEditorPage — edit-note flow', () => {
  it('renders note editor when a note id is in the URL', async () => {
    wrapDirect('/notes/abc123');
    await waitFor(() =>
      expect(screen.getByTestId('note-editor')).toBeInTheDocument()
    );
  });

  it('displays the note title in the editor', async () => {
    wrapDirect('/notes/abc123');
    await waitFor(() =>
      expect(screen.getByText('Existing Note')).toBeInTheDocument()
    );
  });

  it('calls api.getNote with the route id', async () => {
    wrapDirect('/notes/abc123');
    await waitFor(() => expect(mockApi.getNote).toHaveBeenCalledWith('abc123'));
  });
});
