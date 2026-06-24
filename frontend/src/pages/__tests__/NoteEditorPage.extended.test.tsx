/**
 * NoteEditorPage.extended.test.tsx
 * Targets uncovered lines:
 *   170-171 — "Note not found" fallback when !note after load
 *   176-181 — edit-note WikilinkAutocomplete onSelect/onClose paths
 *   210-211 — new-note WikilinkAutocomplete onSelect path
 *   216-221 — new-note WikilinkAutocomplete onClose path
 */
import React from 'react';
import {
  render,
  screen,
  fireEvent,
  waitFor,
  act,
} from '@testing-library/react';
import { describe, it, expect, vi, beforeEach } from 'vitest';
import { MemoryRouter, Route, Routes } from 'react-router-dom';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';

// ---- Mocks -----------------------------------------------------------------
const mockGetNote    = vi.fn();
const mockCreateNote = vi.fn();
const mockUpdateNote = vi.fn();

vi.mock('@/services/api', () => ({
  default: {
    getNote:    (...a: unknown[]) => mockGetNote(...a),
    createNote: (...a: unknown[]) => mockCreateNote(...a),
    updateNote: (...a: unknown[]) => mockUpdateNote(...a),
    listNotes:  vi.fn().mockResolvedValue({ items: [] }),
  },
}));

vi.mock('@/store/useAppStore', () => ({
  useAppStore: () => ({
    token: 'tok',
    user: { id: '1' },
    setActiveNoteId: vi.fn(),
    activeNoteId: null,
    editorMode: 'edit',
    setEditorMode: vi.fn(),
    sidebarCollapsed: false,
    setSidebarCollapsed: vi.fn(),
    toggleSidebar: vi.fn(),
    activeFolder: null,
    setActiveFolder: vi.fn(),
    searchQuery: '',
    setSearchQuery: vi.fn(),
    ragMode: 'hybrid',
    setRagMode: vi.fn(),
    chatMessages: [],
    appendChatMessage: vi.fn(),
    updateLastAssistantMessage: vi.fn(),
    clearChat: vi.fn(),
    sessionId: null,
    setSessionId: vi.fn(),
  }),
}));

vi.mock('@/components/NoteEditor', () => ({
  default: ({
    initialTitle,
    onSave,
  }: {
    initialTitle?: string;
    onSave?: (body: string, title?: string) => void;
  }) => (
    <div data-testid="note-editor">
      <input data-testid="title-input" defaultValue={initialTitle ?? ''} />
      <textarea data-testid="body-input" />
      <button data-testid="save-btn" onClick={() => onSave?.('test body', 'Test Title')}>
        Save
      </button>
    </div>
  ),
}));

vi.mock('@/components/notes/NoteTemplateGallery', () => ({
  NoteTemplateGallery: ({
    onSelect,
    onClose,
  }: {
    onSelect: (t: unknown) => void;
    onClose: () => void;
  }) => (
    <div data-testid="template-gallery">
      <button
        data-testid="template-blank"
        onClick={() =>
          onSelect({
            id: 'blank', name: 'Blank', body: '',
            folder: '10-zettelkasten', note_type: 'permanent',
          })
        }
      >
        Blank
      </button>
      <button data-testid="gallery-close" onClick={onClose}>
        Close
      </button>
    </div>
  ),
}));

// Wikilink autocomplete — controllable via test
let wikilinkQueryValue: string | null = null;
const mockInsertWikilink = vi.fn();

vi.mock('@/components/editor/WikilinkAutocomplete', () => ({
  default: ({
    onSelect,
    onClose,
  }: {
    query: string;
    onSelect: (title: string) => void;
    onClose: () => void;
  }) => (
    <div data-testid="wikilink-popup">
      <button data-testid="wikilink-select" onClick={() => onSelect('My Linked Note')}>
        Select
      </button>
      <button data-testid="wikilink-close" onClick={() => onClose()}>
        Close
      </button>
    </div>
  ),
  useWikilinkDetector: () => ({
    wikilinkQuery: wikilinkQueryValue,
    wikilinkAnchorRect: wikilinkQueryValue !== null ? new DOMRect() : null,
    insertWikilink: mockInsertWikilink,
  }),
}));

import NoteEditorPage from '@/pages/NoteEditorPage';

const NOTE = {
  id: 'note-1',
  title: 'Existing Note',
  slug: 'existing-note',
  body: 'Hello [[World]]',
  body_html: '<p>Hello [[World]]</p>',
  note_type: 'permanent',
  status: 'draft',
  folder: '10-zettelkasten',
  word_count: 2,
  is_deleted: false,
  vector_indexed: false,
  graph_indexed: false,
  tags: [],
  created_at: '2026-01-01T00:00:00Z',
  updated_at: '2026-01-02T00:00:00Z',
};

function makeQC() {
  return new QueryClient({ defaultOptions: { queries: { retry: false } } });
}

function renderEditNote(id = 'note-1') {
  mockGetNote.mockResolvedValue(NOTE);
  mockUpdateNote.mockResolvedValue(NOTE);
  return render(
    <QueryClientProvider client={makeQC()}>
      <MemoryRouter initialEntries={[`/notes/${id}`]}>
        <Routes>
          <Route path="/notes/:id" element={<NoteEditorPage />} />
          <Route path="/notes" element={<div data-testid="notes-page" />} />
        </Routes>
      </MemoryRouter>
    </QueryClientProvider>
  );
}

function renderNewNote() {
  mockCreateNote.mockResolvedValue({ ...NOTE, id: 'note-new' });
  return render(
    <QueryClientProvider client={makeQC()}>
      <MemoryRouter initialEntries={['/notes/new']}>
        <Routes>
          <Route path="/notes/new" element={<NoteEditorPage />} />
          <Route path="/notes/:id" element={<div data-testid="note-detail" />} />
        </Routes>
      </MemoryRouter>
    </QueryClientProvider>
  );
}

describe('NoteEditorPage — new note flow', () => {
  beforeEach(() => { vi.clearAllMocks(); wikilinkQueryValue = null; });

  it('shows template gallery on /notes/new', async () => {
    renderNewNote();
    await waitFor(() => screen.getByTestId('template-gallery'));
  });

  it('selecting blank template shows editor', async () => {
    renderNewNote();
    await waitFor(() => screen.getByTestId('template-gallery'));
    fireEvent.click(screen.getByTestId('template-blank'));
    await waitFor(() => screen.getByTestId('note-editor'));
    expect(screen.queryByTestId('template-gallery')).toBeNull();
  });

  it('save button calls createNote', async () => {
    renderNewNote();
    await waitFor(() => screen.getByTestId('template-gallery'));
    fireEvent.click(screen.getByTestId('template-blank'));
    await waitFor(() => screen.getByTestId('save-btn'));
    fireEvent.click(screen.getByTestId('save-btn'));
    await act(async () => { await new Promise((r) => setTimeout(r, 80)); });
    expect(mockCreateNote).toHaveBeenCalled();
  });

  it('wikilink onSelect calls insertWikilink (lines 210-211)', async () => {
    wikilinkQueryValue = 'World';
    renderNewNote();
    await waitFor(() => screen.getByTestId('template-gallery'));
    fireEvent.click(screen.getByTestId('template-blank'));
    await waitFor(() => screen.getByTestId('wikilink-popup'));
    fireEvent.click(screen.getByTestId('wikilink-select'));
    expect(mockInsertWikilink).toHaveBeenCalledWith('My Linked Note');
  });

  it('wikilink onClose calls insertWikilink with empty string (lines 216-221)', async () => {
    wikilinkQueryValue = 'World';
    renderNewNote();
    await waitFor(() => screen.getByTestId('template-gallery'));
    fireEvent.click(screen.getByTestId('template-blank'));
    await waitFor(() => screen.getByTestId('wikilink-popup'));
    fireEvent.click(screen.getByTestId('wikilink-close'));
    expect(mockInsertWikilink).toHaveBeenCalledWith('');
  });
});

describe('NoteEditorPage — edit note flow', () => {
  beforeEach(() => { vi.clearAllMocks(); wikilinkQueryValue = null; });

  it('renders note editor after note loads', async () => {
    renderEditNote();
    await waitFor(() => screen.getByTestId('note-editor'), { timeout: 3000 });
  });

  it('save button calls updateNote', async () => {
    renderEditNote();
    await waitFor(() => screen.getByTestId('save-btn'), { timeout: 3000 });
    fireEvent.click(screen.getByTestId('save-btn'));
    await act(async () => { await new Promise((r) => setTimeout(r, 80)); });
    expect(mockUpdateNote).toHaveBeenCalled();
  });

  it('does not show template gallery in edit mode', async () => {
    renderEditNote();
    await waitFor(() => screen.getByTestId('note-editor'), { timeout: 3000 });
    expect(screen.queryByTestId('template-gallery')).toBeNull();
  });

  it('wikilink onSelect in edit mode calls insertWikilink (lines 176-181)', async () => {
    wikilinkQueryValue = 'World';
    renderEditNote();
    await waitFor(() => screen.getByTestId('wikilink-popup'), { timeout: 3000 });
    fireEvent.click(screen.getByTestId('wikilink-select'));
    expect(mockInsertWikilink).toHaveBeenCalledWith('My Linked Note');
  });

  it('wikilink onClose in edit mode calls insertWikilink with empty string', async () => {
    wikilinkQueryValue = 'World';
    renderEditNote();
    await waitFor(() => screen.getByTestId('wikilink-popup'), { timeout: 3000 });
    fireEvent.click(screen.getByTestId('wikilink-close'));
    expect(mockInsertWikilink).toHaveBeenCalledWith('');
  });
});

describe('NoteEditorPage — note not found (lines 170-171)', () => {
  beforeEach(() => { vi.clearAllMocks(); wikilinkQueryValue = null; });

  it('shows "Note not found" when getNote resolves null', async () => {
    // getNote resolves successfully but returns null (note deleted/missing)
    mockGetNote.mockResolvedValue(null);
    render(
      <QueryClientProvider client={makeQC()}>
        <MemoryRouter initialEntries={['/notes/ghost-note']}>
          <Routes>
            <Route path="/notes/:id" element={<NoteEditorPage />} />
          </Routes>
        </MemoryRouter>
      </QueryClientProvider>
    );
    await waitFor(() =>
      expect(screen.getByText(/Note not found/i)).toBeTruthy(),
      { timeout: 3000 }
    );
  });
});
