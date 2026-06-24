import { describe, it, expect, vi } from 'vitest';
import { render, screen } from '@testing-library/react';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { MemoryRouter, Route, Routes } from 'react-router-dom';
import { createElement } from 'react';
import { makeNote } from '../../test/factories';

// Mock the entire hooks/useNotes module.
vi.mock('../../hooks/useNotes', () => ({
  useNote:       vi.fn(() => ({ data: makeNote({ title: 'Editor Test Note' }), isLoading: false })),
  useUpdateNote: vi.fn(() => ({ mutateAsync: vi.fn(), mutate: vi.fn(), isPending: false })),
  useNotes:      vi.fn(() => ({ data: [], isLoading: false })),
  useNotesList:  vi.fn(() => ({ data: [], isLoading: false })),
  useCreateNote: vi.fn(() => ({ mutateAsync: vi.fn(), isPending: false })),
  useDeleteNote: vi.fn(() => ({ mutateAsync: vi.fn(), isPending: false })),
  useBacklinks:  vi.fn(() => ({ data: { backlinks: [] }, isLoading: false })),
  useDailyNote:  vi.fn(() => ({ data: undefined, isLoading: false })),
}));

// Mock heavy sub-components
vi.mock('../../components/notes/NoteTemplateGallery', () => ({
  NoteTemplateGallery: ({ onClose }: { onClose: () => void }) => (
    createElement('div', { 'data-testid': 'template-gallery' },
      createElement('button', { onClick: onClose }, 'Close')
    )
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
  const qc = new QueryClient();
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
  // FrontmatterPanel is mocked as an empty div — the title input lives
  // inside it and is therefore not in the DOM. Assert the editor itself
  // is present instead.
  it('renders the note editor area', () => {
    wrap();
    expect(screen.getByTestId('note-editor')).toBeInTheDocument();
  });

  it('shows Edit and Preview toggle buttons', () => {
    wrap();
    expect(screen.getByRole('button', { name: /edit/i })).toBeInTheDocument();
    expect(screen.getByRole('button', { name: /preview/i })).toBeInTheDocument();
  });
});
