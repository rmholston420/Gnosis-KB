/**
 * NoteEditorPage — extended tests
 * ================================
 * Mocks ../../hooks/useNotes (the actual data layer used by NoteEditorPage)
 * so that individual hook calls are interceptable.
 */
import React from 'react';
import { render, screen, fireEvent, waitFor, act } from '@testing-library/react';
import { vi, describe, it, beforeEach, expect } from 'vitest';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { MemoryRouter, Routes, Route } from 'react-router-dom';

// ── Use vi.hoisted so these are available inside the vi.mock factory ──────────
const { mockMutateAsync, mockMutate, mockUpdateNote } = vi.hoisted(() => {
  const mockMutateAsync = vi.fn();
  const mockMutate      = vi.fn();
  const mockUpdateNote  = vi.fn(() => ({
    mutateAsync: mockMutateAsync,
    mutate:      mockMutate,
    isPending:   false,
  }));
  return { mockMutateAsync, mockMutate, mockUpdateNote };
});

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
  frontmatter:   {},
  outgoing_links: [] as unknown[],
  incoming_links: [] as unknown[],
  created_at:  '',
  updated_at:  '',
};

vi.mock('../../hooks/useNotes', () => ({
  useNote:       vi.fn(() => ({ data: NOTE_STUB, isLoading: false })),
  useUpdateNote: mockUpdateNote,
  useNotes:      vi.fn(() => ({ data: [], isLoading: false })),
  useNotesList:  vi.fn(() => ({ data: [], isLoading: false })),
  useCreateNote: vi.fn(() => ({ mutateAsync: vi.fn(), isPending: false })),
  useDeleteNote: vi.fn(() => ({ mutateAsync: vi.fn(), isPending: false })),
  useBacklinks:  vi.fn(() => ({ data: { backlinks: [] }, isLoading: false })),
  useDailyNote:  vi.fn(() => ({ data: undefined, isLoading: false })),
}));

// ── Wikilink autocomplete mock ────────────────────────────────────────────────
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
    anchorRect:     null,
    insertWikilink: mockInsertWikilink,
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

vi.mock('../../components/NoteEditor', () => ({
  default: ({ onSave }: { onSave: (body: string) => void }) => (
    <div data-testid="note-editor">
      <button data-testid="editor-save" onClick={() => onSave('test body')}>Save</button>
    </div>
  ),
}));

import NoteEditorPage from '../NoteEditorPage';

// ── Helpers ───────────────────────────────────────────────────────────────────
function makeQueryClient() {
  return new QueryClient({
    defaultOptions: {
      queries:   { retry: false, gcTime: 0, staleTime: 0 },
      mutations: { retry: false },
    },
  });
}

function renderNewNote() {
  const qc = makeQueryClient();
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
  wikilinkQueryValue = null;
  mockInsertWikilink = vi.fn();
  mockMutateAsync.mockReset();
  mockMutate.mockReset();
  mockMutateAsync.mockResolvedValue(NOTE_STUB);
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

  it('save button triggers a mutation in new note mode', async () => {
    renderNewNote();
    await waitFor(() => screen.getByTestId('template-gallery'));
    fireEvent.click(screen.getByText('Close'));
    await waitFor(() => screen.getByTestId('save-btn'));
    fireEvent.click(screen.getByTestId('save-btn'));
    await act(async () => { await new Promise((r) => setTimeout(r, 80)); });
    expect(mockMutate).toHaveBeenCalled();
  });
});

describe('NoteEditorPage — edit note flow', () => {
  it('renders note editor after note loads', async () => {
    renderEditNote();
    await waitFor(() => screen.getByTestId('note-editor'), { timeout: 3000 });
  });

  it('save button calls updateMutation in edit mode', async () => {
    renderEditNote();
    await waitFor(() => screen.getByTestId('save-btn'), { timeout: 3000 });
    fireEvent.click(screen.getByTestId('save-btn'));
    await act(async () => { await new Promise((r) => setTimeout(r, 80)); });
    expect(mockMutate).toHaveBeenCalled();
  });

  it('does not show template gallery in edit mode', async () => {
    renderEditNote();
    await waitFor(() => screen.getByTestId('note-editor'), { timeout: 3000 });
    expect(screen.queryByTestId('template-gallery')).toBeNull();
  });

  it('wikilink onSelect in edit mode calls insertWikilink', async () => {
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
