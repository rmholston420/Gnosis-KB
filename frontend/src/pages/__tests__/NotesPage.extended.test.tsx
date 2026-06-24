/**
 * NotesPage.extended.test.tsx
 * Covers note list load, loading skeleton, empty state, new note creation,
 * note selection, save, folder filter, and no-active-note state.
 * Uncovered lines: 31-39, 43-46, 85, 102
 */
import React from 'react';
import { render, screen, fireEvent, waitFor, act } from '@testing-library/react';
import { describe, it, expect, vi, beforeEach } from 'vitest';
import { MemoryRouter } from 'react-router-dom';

// ---- Mocks -----------------------------------------------------------------
const mockListNotes   = vi.fn();
const mockCreateNote  = vi.fn();
const mockUpdateNote  = vi.fn();

vi.mock('@/services/api', () => ({
  default: {
    listNotes:  (...a: unknown[]) => mockListNotes(...a),
    createNote: (...a: unknown[]) => mockCreateNote(...a),
    updateNote: (...a: unknown[]) => mockUpdateNote(...a),
  },
}));

// useAppStore — plain Zustand store, no selector
let mockActiveFolder: string | null = null;
let mockActiveNoteId: string | null = null;
const mockSetActiveNoteId = vi.fn((id: string | null) => { mockActiveNoteId = id; });

vi.mock('@/store/useAppStore', () => ({
  useAppStore: () => ({
    activeFolder: mockActiveFolder,
    activeNoteId: mockActiveNoteId,
    setActiveNoteId: mockSetActiveNoteId,
  }),
}));

// NoteEditor stub
vi.mock('@/components/NoteEditor', () => ({
  default: ({ note, onSave }: { note: { title: string }; onSave: (body: string, title: string) => Promise<void> }) => (
    <div data-testid="note-editor">
      <span data-testid="editor-title">{note.title}</span>
      <button
        data-testid="editor-save"
        onClick={() => onSave('updated body', 'Updated Title')}
      >
        Save
      </button>
    </div>
  ),
}));

import NotesPage from '@/pages/NotesPage';

const NOTES = [
  { id: 'n1', title: 'Note Alpha', folder: '10-zettelkasten', body: '', tags: [], slug: 'note-alpha',
    note_type: 'permanent', status: 'draft', word_count: 2, is_deleted: false,
    vector_indexed: false, graph_indexed: false, created_at: '', updated_at: '' },
  { id: 'n2', title: 'Note Beta', folder: '00-inbox', body: '', tags: [], slug: 'note-beta',
    note_type: 'fleeting', status: 'draft', word_count: 1, is_deleted: false,
    vector_indexed: false, graph_indexed: false, created_at: '', updated_at: '' },
];

function renderPage() {
  return render(
    <MemoryRouter>
      <NotesPage />
    </MemoryRouter>
  );
}

describe('NotesPage', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    mockActiveFolder = null;
    mockActiveNoteId = null;
  });

  it('shows loading skeletons while fetching', async () => {
    mockListNotes.mockImplementation(
      () => new Promise((r) => setTimeout(() => r({ items: NOTES }), 300))
    );
    renderPage();
    // skeleton divs are rendered during load
    const skels = document.querySelectorAll('.skeleton');
    expect(skels.length).toBeGreaterThan(0);
  });

  it('renders note list after load', async () => {
    mockListNotes.mockResolvedValue({ items: NOTES });
    renderPage();
    await waitFor(() => screen.getByText('Note Alpha'));
    expect(screen.getByText('Note Beta')).toBeTruthy();
  });

  it('shows empty state when no notes', async () => {
    mockListNotes.mockResolvedValue({ items: [] });
    renderPage();
    await waitFor(() => screen.getByText(/No notes here yet/i));
  });

  it('shows "All Notes" label when no activeFolder', async () => {
    mockListNotes.mockResolvedValue({ items: [] });
    renderPage();
    await waitFor(() => screen.getByText(/All Notes/i));
  });

  it('shows folder name when activeFolder is set', async () => {
    mockActiveFolder = '10-zettelkasten';
    mockListNotes.mockResolvedValue({ items: [] });
    renderPage();
    await waitFor(() => screen.getByText('10-zettelkasten'));
  });

  it('clicking a note calls setActiveNoteId', async () => {
    mockListNotes.mockResolvedValue({ items: NOTES });
    renderPage();
    await waitFor(() => screen.getByText('Note Alpha'));
    fireEvent.click(screen.getByText('Note Alpha'));
    expect(mockSetActiveNoteId).toHaveBeenCalledWith('n1');
  });

  it('new note button calls createNote and selects new note', async () => {
    mockListNotes.mockResolvedValue({ items: [] });
    mockCreateNote.mockResolvedValue({ ...NOTES[0], id: 'new-1', title: 'Untitled' });
    renderPage();
    await waitFor(() => screen.queryByText(/No notes here yet/i));
    fireEvent.click(screen.getByTitle('New note'));
    await waitFor(() => expect(mockCreateNote).toHaveBeenCalled());
    expect(mockSetActiveNoteId).toHaveBeenCalledWith('new-1');
  });

  it('shows editor when a note is active', async () => {
    mockActiveNoteId = 'n1';
    mockListNotes.mockResolvedValue({ items: NOTES });
    renderPage();
    await waitFor(() => screen.getByTestId('note-editor'));
    expect(screen.getByTestId('editor-title').textContent).toBe('Note Alpha');
  });

  it('save calls updateNote with body and title', async () => {
    mockActiveNoteId = 'n1';
    mockListNotes.mockResolvedValue({ items: NOTES });
    mockUpdateNote.mockResolvedValue({ ...NOTES[0], body: 'updated body', title: 'Updated Title' });
    renderPage();
    await waitFor(() => screen.getByTestId('editor-save'));
    fireEvent.click(screen.getByTestId('editor-save'));
    await waitFor(() =>
      expect(mockUpdateNote).toHaveBeenCalledWith('n1', {
        body: 'updated body',
        title: 'Updated Title',
      })
    );
  });

  it('shows empty editor prompt when no note selected', async () => {
    mockListNotes.mockResolvedValue({ items: NOTES });
    renderPage();
    await waitFor(() => screen.getByText(/Select a note or create a new one/i));
  });

  it('listNotes is called with folder param when activeFolder is set', async () => {
    mockActiveFolder = '10-zettelkasten';
    mockListNotes.mockResolvedValue({ items: [] });
    renderPage();
    await waitFor(() => expect(mockListNotes).toHaveBeenCalledWith(
      expect.objectContaining({ folder: '10-zettelkasten' })
    ));
  });
});
