import { describe, it, expect, vi } from 'vitest';
import { render, screen, waitFor } from '@testing-library/react';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { MemoryRouter } from 'react-router-dom';
import { createElement } from 'react';
import { makeNote } from '../../test/factories';

// Mock api.listNotes — NotesPage uses raw useQuery(api.listNotes)
const mockListNotes  = vi.fn();
const mockCreateNote = vi.fn();
vi.mock('../../services/api', () => ({
  default: {
    listNotes:  (...a: unknown[]) => mockListNotes(...a),
    createNote: (...a: unknown[]) => mockCreateNote(...a),
  },
}));

import NotesPage from '../NotesPage';

function wrap(ui: React.ReactNode = createElement(NotesPage)) {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(
    createElement(QueryClientProvider, { client: qc },
      createElement(MemoryRouter, null, ui)
    )
  );
}

describe('NotesPage', () => {
  it('renders page heading', async () => {
    mockListNotes.mockResolvedValue([makeNote({ title: 'My First Note' })]);
    wrap();
    await waitFor(() =>
      expect(screen.getByRole('heading', { name: /notes/i })).toBeInTheDocument()
    );
  });

  it('renders note list items', async () => {
    mockListNotes.mockResolvedValue([makeNote({ title: 'My First Note' })]);
    wrap();
    await waitFor(() =>
      expect(screen.getByText('My First Note')).toBeInTheDocument()
    );
  });
});
