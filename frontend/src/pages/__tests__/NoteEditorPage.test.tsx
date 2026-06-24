import { describe, it, expect, vi } from 'vitest';
import { render, screen } from '@testing-library/react';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { MemoryRouter, Route, Routes } from 'react-router-dom';
import { createElement } from 'react';
import { makeNote } from '../../test/factories';

vi.mock('../../hooks/useNotes', () => ({
  useNote:       vi.fn(() => ({ data: makeNote({ title: 'Editor Test Note' }), isLoading: false })),
  useUpdateNote: vi.fn(() => ({ mutateAsync: vi.fn(), isPending: false })),
  useCreateNote: vi.fn(() => ({ mutateAsync: vi.fn(), isPending: false })),
  useDeleteNote: vi.fn(() => ({ mutateAsync: vi.fn(), isPending: false })),
}));
vi.mock('../../store/editorStore', () => ({
  useEditorStore: vi.fn(() => ({
    title: 'Editor Test Note', body: '# Test', mode: 'edit',
    pendingChanges: false,
    setTitle: vi.fn(), setBody: vi.fn(), setMode: vi.fn(), reset: vi.fn(),
  })),
}));

import NoteEditorPage from '../NoteEditorPage';

function wrap(noteId = 'note-001') {
  const qc = new QueryClient();
  return render(
    createElement(
      QueryClientProvider, { client: qc },
      createElement(
        MemoryRouter, { initialEntries: [`/notes/${noteId}/edit`] },
        createElement(Routes, null,
          createElement(Route, { path: '/notes/:noteId/edit', element: createElement(NoteEditorPage) })
        )
      )
    )
  );
}

describe('NoteEditorPage', () => {
  it('renders the note title', () => {
    wrap();
    expect(screen.getByDisplayValue('Editor Test Note')).toBeInTheDocument();
  });

  it('shows Edit and Preview toggle buttons', () => {
    wrap();
    expect(screen.getByRole('button', { name: /edit/i })).toBeInTheDocument();
    expect(screen.getByRole('button', { name: /preview/i })).toBeInTheDocument();
  });
});
