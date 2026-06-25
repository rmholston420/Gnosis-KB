/**
 * NoteEditorPage.test.tsx
 * =======================
 * NoteEditorPage imports getNote / createNote / updateNote / listNotes
 * directly from '../../api/notes' (named imports for spy compatibility).
 * Mocking '../../hooks/useNotes' has no effect — we must mock the api layer.
 */
import { describe, it, expect, vi } from 'vitest';
import { render, screen, waitFor } from '@testing-library/react';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { MemoryRouter, Route, Routes } from 'react-router-dom';
import { createElement } from 'react';
import { makeNote } from '../../test/factories';

const STUB = makeNote({ title: 'Editor Test Note' });

// Mock the API layer that NoteEditorPage actually calls
vi.mock('../../api/notes', () => ({
  getNote:    vi.fn().mockResolvedValue(STUB),
  updateNote: vi.fn().mockResolvedValue(STUB),
  createNote: vi.fn().mockResolvedValue(STUB),
  listNotes:  vi.fn().mockResolvedValue({ items: [STUB] }),
}));

// Mock heavy sub-components
vi.mock('../../components/notes/NoteTemplateGallery', () => ({
  NoteTemplateGallery: ({ onClose }: { onClose: () => void }) =>
    createElement('div', { 'data-testid': 'template-gallery' },
      createElement('button', { onClick: onClose }, 'Close')
    ),
}));

vi.mock('../../components/ai/AiSidebar', () => ({
  AiSidebar: () => createElement('div', { 'data-testid': 'ai-sidebar' }),
}));

vi.mock('../../components/editor/BacklinksPanel', () => ({
  BacklinksPanel: () => createElement('div', { 'data-testid': 'backlinks-panel' }),
}));

vi.mock('../../components/editor/FrontmatterPanel', () => ({
  FrontmatterPanel: () => createElement('div', { 'data-testid': 'frontmatter-panel' }),
}));

vi.mock('../../components/shared/MarkdownPreview', () => ({
  MarkdownPreview: ({ content }: { content: string }) =>
    createElement('div', { 'data-testid': 'markdown-preview' }, content),
}));

vi.mock('../../components/layout/SplitPane', () => ({
  SplitPane: ({ left, right }: { left: React.ReactNode; right: React.ReactNode }) =>
    createElement('div', null,
      createElement('div', { 'data-testid': 'split-left' },  left),
      createElement('div', { 'data-testid': 'split-right' }, right),
    ),
}));

vi.mock('../../components/NoteEditor', () => ({
  default: ({ onSave }: { onSave: (b: string) => void }) =>
    createElement('div', { 'data-testid': 'note-editor' },
      createElement('button', { 'data-testid': 'editor-save', onClick: () => onSave('body') }, 'Save')
    ),
}));

import NoteEditorPage from '../NoteEditorPage';

function wrap(noteId = 'note-001') {
  const qc = new QueryClient({
    defaultOptions: { queries: { retry: false }, mutations: { retry: false } },
  });
  return render(
    createElement(
      QueryClientProvider, { client: qc },
      createElement(
        MemoryRouter, { initialEntries: [`/notes/${noteId}`] },
        createElement(Routes, null,
          createElement(Route, { path: '/notes/:id', element: createElement(NoteEditorPage) })
        )
      )
    )
  );
}

describe('NoteEditorPage', () => {
  it('renders the note editor area', async () => {
    wrap();
    await waitFor(() =>
      expect(screen.getByTestId('note-editor')).toBeInTheDocument()
    );
  });

  it('shows Edit and Preview toggle buttons', async () => {
    wrap();
    await waitFor(() => {
      expect(screen.getByRole('button', { name: /edit/i })).toBeInTheDocument();
      expect(screen.getByRole('button', { name: /preview/i })).toBeInTheDocument();
    });
  });
});
