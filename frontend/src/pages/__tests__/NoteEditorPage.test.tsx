import { describe, it, expect, vi } from 'vitest';
import { render, screen } from '@testing-library/react';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { MemoryRouter, Route, Routes } from 'react-router-dom';
import { createElement } from 'react';
import { makeNote } from '../../test/factories';

// NoteEditorPage now uses useNote / useUpdateNote / useNotes hooks
vi.mock('../../hooks/useNotes', () => ({
  useNote:       vi.fn(() => ({ data: makeNote({ title: 'Editor Test Note' }), isLoading: false })),
  useUpdateNote: vi.fn(() => ({ mutateAsync: vi.fn(), mutate: vi.fn(), isPending: false })),
  useNotes:      vi.fn(() => ({ data: [], isLoading: false })),
  useCreateNote: vi.fn(() => ({ mutateAsync: vi.fn(), isPending: false })),
  useDeleteNote: vi.fn(() => ({ mutateAsync: vi.fn(), isPending: false })),
}));

// Mock the template gallery so it doesn't block render for edit-mode tests
vi.mock('../../components/notes/NoteTemplateGallery', () => ({
  NoteTemplateGallery: ({ onClose }: { onClose: () => void }) => (
    createElement('div', { 'data-testid': 'template-gallery' },
      createElement('button', { onClick: onClose }, 'Close')
    )
  ),
}));

import NoteEditorPage from '../NoteEditorPage';

// Route uses :id — matches what NoteEditorPage reads via useParams
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
