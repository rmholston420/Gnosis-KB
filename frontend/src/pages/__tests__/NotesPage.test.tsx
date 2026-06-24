import { describe, it, expect, vi } from 'vitest';
import { render, screen } from '@testing-library/react';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { MemoryRouter } from 'react-router-dom';
import { createElement } from 'react';
import { makeListItem } from '../../test/factories';

vi.mock('../../hooks/useNotes', () => ({
  useNotesList: vi.fn(() => ({
    data: { items: [makeListItem({ title: 'My First Note' })], total: 1, pages: 1 },
    isLoading: false,
    isError:   false,
  })),
}));

import NotesPage from '../NotesPage';

function wrap(ui: React.ReactNode) {
  const qc = new QueryClient();
  return render(createElement(QueryClientProvider, { client: qc }, createElement(MemoryRouter, null, ui)));
}

describe('NotesPage', () => {
  it('renders page heading', () => {
    wrap(<NotesPage />);
    expect(screen.getByRole('heading', { name: /notes/i })).toBeInTheDocument();
  });

  it('renders note list items', () => {
    wrap(<NotesPage />);
    expect(screen.getByText('My First Note')).toBeInTheDocument();
  });
});
