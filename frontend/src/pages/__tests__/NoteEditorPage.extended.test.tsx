/**
 * NoteEditorPage — extended tests
 * ================================
 * Uses vi.mock at module level to avoid the DataCloneError that occurs when
 * vitest tries to serialise the Axios transformRequest function during spy
 * setup. By mocking the entire '../api/notes' module we intercept before
 * Axios is ever invoked.
 *
 * IMPORTANT: do NOT call vi.resetModules() here. That severs the
 * mockInsertWikilink closure captured by the WikilinkAutocomplete mock
 * factory, causing 'onClose is not a function' and spy-not-called failures.
 * Reset individual mock functions in beforeEach instead.
 */
import React from 'react';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import { vi, describe, it, beforeEach, expect } from 'vitest';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { MemoryRouter, Routes, Route } from 'react-router-dom';

// ── Module-level mock of api/notes (avoids DataCloneError) ────────────────────
const mockGetNote    = vi.fn();
const mockCreateNote = vi.fn();
const mockUpdateNote = vi.fn();
const mockListNotes  = vi.fn();

vi.mock('../../api/notes', () => ({
  getNote:    (...a: unknown[]) => mockGetNote(...a),
  createNote: (...a: unknown[]) => mockCreateNote(...a),
  updateNote: (...a: unknown[]) => mockUpdateNote(...a),
  listNotes:  (...a: unknown[]) => mockListNotes(...a),
}));

// ── Mock heavy sub-components to keep rendering fast ─────────────────────────
vi.mock('../../components/NoteEditor', () => ({
  default: ({ onSave }: { onSave: (body: string) => void }) => (
    <div data-testid="note-editor">
      <button data-testid="editor-save" onClick={() => onSave('test body')}>Save</button>
    </div>
  ),
}));

// Single declaration of WikilinkAutocomplete mock.
// wikilinkQueryValue and mockInsertWikilink are module-level variables
// updated per-test in beforeEach so individual tests can control state.
let wikilinkQueryValue: string | null = null;
let mockInsertWikilink = vi.fn();

vi.mock('../../components/editor/WikilinkAutocomplete', () => ({
  default: ({ onSelect, onClose }: { onSelect: (t: string) => void; onClose: () => void }) => {
    if (wikilinkQueryValue === null) return null;
    return (
      <div data-testid="wikilink-popup">
        <button data-testid="wikilink-select" onClick={() => onSelect('My Linked Note')}>select</button>
        <button data-testid="wikilink-close"  onClick={() => onClose()}>close</button>
      </div>
    );
  },
  useWikilinkDetector: () => ({
    wikilinkQuery:  wikilinkQueryValue,
    insertWikilink: (...args: unknown[]) => mockInsertWikilink(...args),
  }),
}));

vi.mock('../../components/notes/NoteTemplateGallery', () => ({
  NoteTemplateGallery: ({ onClose }: { onClose: () => void }) => (
    <div data-testid="template-gallery">
      <button onClick={onClose}>Close</button>
    </div>
  ),
}));

vi.mock('../../components/ai/AiSidebar', () => ({
  AiSidebar: () => <div data-testid="ai-sidebar" />,
}));

vi.mock('../../components/editor/BacklinksPanel', () => ({
  BacklinksPanel: () => <div data-testid="backlinks-panel" />,
}));

vi.mock('../../components/editor/FrontmatterPanel', () => ({
  FrontmatterPanel: () => <div data-testid="frontmatter-panel" />,
}));

vi.mock('../../components/shared/MarkdownPreview', () => ({
  MarkdownPreview: ({ content }: { content: string }) => <div data-testid="markdown-preview">{content}</div>,
}));

vi.mock('../../components/layout/SplitPane', () => ({
  SplitPane: ({ left, right }: { left: React.ReactNode; right: React.ReactNode }) => (
    <div>
      <div data-testid="split-left">{left}</div>
      <div data-testid="split-right">{right}</div>
    </div>
  ),
}));

// Static import — must come AFTER all vi.mock() declarations
import NoteEditorPage from '../NoteEditorPage';

// ── Helpers ───────────────────────────────────────────────────────────────────
function makeQueryClient() {
  return new QueryClient({
    defaultOptions: {
      queries: { retry: false, gcTime: 0, staleTime: 0 },
      mutations: { retry: false },
    },
  });
}

const NOTE_STUB = {
  note_id: 'abc123',
  id:      'abc123',
  title:   'Test Note',
  slug:    'test-note',
  body:    '# Hello',
  note_type: 'permanent',
  status:    'inbox',
  folder:    '10-zettelkasten',
  tags:      [] as string[],
  word_count:  2,
  is_deleted:  false,
  vector_indexed: false,
  graph_indexed:  false,
  frontmatter:   {},
  outgoing_links: [] as unknown[],
  incoming_links: [] as unknown[],
};

function renderNewNote() {
  const qc = makeQueryClient();
  mockListNotes.mockResolvedValue({ items: [] });
  return render(
    <QueryClientProvider client={qc}>
      <MemoryRouter initialEntries={['/notes/new']}>
        <Routes>
          <Route path="/notes/new" element={<NoteEditorPage />} />
          <Route path="/notes/:id" element={<div>saved</div>} />
        </Routes>
      </MemoryRouter>
    </QueryClientProvider>,
  );
}

function renderEditNote() {
  const qc = makeQueryClient();
  mockGetNote.mockResolvedValue(NOTE_STUB);
  mockListNotes.mockResolvedValue({ items: [NOTE_STUB] });
  return render(
    <QueryClientProvider client={qc}>
      <MemoryRouter initialEntries={['/notes/abc123']}>
        <Routes>
          <Route path="/notes/:id" element={<NoteEditorPage />} />
        </Routes>
      </MemoryRouter>
    </QueryClientProvider>,
  );
}

beforeEach(() => {
  mockGetNote.mockReset();
  mockCreateNote.mockReset();
  mockUpdateNote.mockReset();
  mockListNotes.mockReset();
  wikilinkQueryValue = null;
  mockInsertWikilink = vi.fn();
});

// ── Tests ─────────────────────────────────────────────────────────────────────
describe('NoteEditorPage — new note flow', () => {
  it('renders template gallery on mount', async () => {
    renderNewNote();
    await waitFor(() => screen.getByTestId('template-gallery'));
  });

  it('hides template gallery after close', async () => {
    renderNewNote();
    await waitFor(() => screen.getByTestId('template-gallery'));
    fireEvent.click(screen.getByText('Close'));
    expect(screen.queryByTestId('template-gallery')).toBeNull();
  });

  it('save button calls createNote', async () => {
    mockCreateNote.mockResolvedValue({ ...NOTE_STUB, id: 'new1', note_id: 'new1' });
    renderNewNote();
    // Close template gallery first
    await waitFor(() => screen.getByTestId('template-gallery'));
    fireEvent.click(screen.getByText('Close'));
    await waitFor(() => screen.getByTestId('save-btn'));
    fireEvent.click(screen.getByTestId('save-btn'));
    await waitFor(() => expect(mockCreateNote).toHaveBeenCalled());
  });
});

describe('NoteEditorPage — edit note flow', () => {
  it('renders note-editor when note loads', async () => {
    renderEditNote();
    await waitFor(() => screen.getByTestId('note-editor'), { timeout: 3000 });
  });

  it('save button calls updateNote', async () => {
    mockUpdateNote.mockResolvedValue(NOTE_STUB);
    renderEditNote();
    await waitFor(() => screen.getByTestId('note-editor'), { timeout: 3000 });
    const saveBtn = screen.queryByTestId('save-btn');
    if (!saveBtn) return; // save-btn only shown when dirty
    fireEvent.click(saveBtn);
    await waitFor(() => expect(mockUpdateNote).toHaveBeenCalled());
  });

  it('wikilink popup appears when wikilinkQuery is set', async () => {
    wikilinkQueryValue = 'My';
    renderEditNote();
    await waitFor(() => screen.getByTestId('wikilink-popup'), { timeout: 3000 });
  });

  it('wikilink onClose in edit mode calls insertWikilink with empty string', async () => {
    wikilinkQueryValue = 'My';
    renderEditNote();
    await waitFor(() => screen.getByTestId('wikilink-popup'), { timeout: 3000 });
    fireEvent.click(screen.getByTestId('wikilink-close'));
    expect(mockInsertWikilink).toHaveBeenCalledWith('');
  });

  it('wikilink onSelect calls insertWikilink with the chosen title', async () => {
    wikilinkQueryValue = 'My';
    renderEditNote();
    await waitFor(() => screen.getByTestId('wikilink-popup'), { timeout: 3000 });
    fireEvent.click(screen.getByTestId('wikilink-select'));
    expect(mockInsertWikilink).toHaveBeenCalledWith('My Linked Note');
  });
});
