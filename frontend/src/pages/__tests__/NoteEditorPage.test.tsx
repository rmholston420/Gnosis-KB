/**
 * NoteEditorPage.test.tsx
 * =======================
 * NoteEditorPage imports getNote / createNote / updateNote / listNotes
 * directly from '../../api/notes' (named imports for spy compatibility).
 * Mocking '../../hooks/useNotes' has no effect — we must mock the api layer.
 *
 * IMPORTANT: Do NOT use top-level variables inside vi.mock() factories.
 * vi.mock() is hoisted to the top of the file by Vitest, so any reference
 * to a const/let declared after the import block will throw a TDZ
 * ReferenceError. Build fixture values inline inside the factory instead.
 */
import { describe, it, expect, vi } from 'vitest';
import { render, screen, waitFor } from '@testing-library/react';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { MemoryRouter, Route, Routes } from 'react-router-dom';
import { createElement } from 'react';
import { makeNote } from '../../test/factories';

// Mock the API layer that NoteEditorPage actually calls.
// Build the stub INSIDE the factory (no top-level variable reference).
vi.mock('../../api/notes', () => {
  const stub = {
    note_id: 'stub-001',
    id:      'stub-001',
    title:   'Editor Test Note',
    body:    '# Editor Test Note\n\nBody.',
    note_type: 'permanent',
    status:    'active',
    tags:      [],
    folder:    'inbox',
    word_count: 4,
    created_at:  '2025-01-01T00:00:00Z',
    updated_at:  '2025-01-01T00:00:00Z',
    modified_at: '2025-01-01T00:00:00Z',
  };
  return {
    getNote:    vi.fn().mockResolvedValue(stub),
    updateNote: vi.fn().mockResolvedValue(stub),
    createNote: vi.fn().mockResolvedValue(stub),
    listNotes:  vi.fn().mockResolvedValue([stub]),
    getBacklinks: vi.fn().mockResolvedValue({ backlinks: [] }),
  };
});

vi.mock('../../components/NoteEditor', () => ({
  default: () => createElement('div', { 'data-testid': 'note-editor' }, 'Editor Stub'),
}));

vi.mock('../../components/editor/WikilinkAutocomplete', () => ({
  default: () => null,
  useWikilinkDetector: () => ({ wikilinkQuery: null, insertWikilink: vi.fn() }),
}));

vi.mock('../../components/AiSidebar', () => ({
  default: () => createElement('div', { 'data-testid': 'ai-sidebar' }, 'AI Sidebar Stub'),
}));

vi.mock('../../components/BacklinkPanel', () => ({
  default: () => createElement('div', { 'data-testid': 'backlink-panel' }, 'Backlink Panel Stub'),
}));

vi.mock('../../components/FrontmatterPanel', () => ({
  default: () => null,
}));

import NoteEditorPage from '../NoteEditorPage';

const STUB = makeNote({ title: 'Editor Test Note' });

function makeWrapper() {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false }, mutations: { retry: false } } });
  return ({ children }: { children: React.ReactNode }) =>
    createElement(QueryClientProvider, { client: qc }, children);
}

function renderEditor(noteId = 'stub-001') {
  return render(
    createElement(
      makeWrapper(),
      null,
      createElement(
        MemoryRouter,
        { initialEntries: [`/notes/${noteId}`] },
        createElement(
          Routes,
          null,
          createElement(Route, { path: '/notes/:id', element: createElement(NoteEditorPage) }),
          createElement(Route, { path: '/notes/new', element: createElement(NoteEditorPage) }),
        ),
      ),
    ),
  );
}

describe('NoteEditorPage', () => {
  it('renders the editor for an existing note', async () => {
    renderEditor(STUB.note_id);
    await waitFor(() => screen.getByTestId('note-editor'));
    expect(screen.getByTestId('note-editor')).toBeInTheDocument();
  });

  it('renders without crashing for a new note', () => {
    renderEditor('new');
    expect(document.body).toBeInTheDocument();
  });
});
