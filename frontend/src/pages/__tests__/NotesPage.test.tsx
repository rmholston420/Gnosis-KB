import { describe, it, expect, vi } from 'vitest';
import { render, screen } from '@testing-library/react';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { MemoryRouter } from 'react-router-dom';
import { createElement } from 'react';
import { makeNote } from '../../test/factories';

// Mock the hooks module — useNotesList is what NotesPage now uses
vi.mock('../../hooks/useNotes', () => ({
  useNotesList: vi.fn(() => ({
    data: [makeNote({ title: 'My First Note' })],
    isLoading: false,
    isError:   false,
  })),
  useCreateNote: vi.fn(() => ({
    mutateAsync: vi.fn(),
    isPending:   false,
  })),
}));

import NotesPage from '../NotesPage';

function wrap(ui: React.ReactNode = createElement(NotesPage)) {
  const qc = new QueryClient();
  return render(
    createElement(QueryClientProvider, { client: qc },
      createElement(MemoryRouter, null, ui)
    )
  );
}

describe('NotesPage', () => {
  it('renders page heading', () => {
    wrap();
    expect(screen.getByRole('heading', { name: /notes/i })).toBeInTheDocument();
  });

  it('renders note list items', () => {
    wrap();
    expect(screen.getByText('My First Note')).toBeInTheDocument();
  });
});
