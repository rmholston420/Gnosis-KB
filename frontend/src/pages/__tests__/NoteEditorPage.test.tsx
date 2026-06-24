/**
 * NoteEditorPage.test.tsx
 * Spy on `getNote` (the real export from api/notes).
 */
import React from 'react';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { MemoryRouter, Route, Routes } from 'react-router-dom';
import { vi, describe, it, expect, beforeEach } from 'vitest';
import * as notesApi from '../../api/notes';
import NoteEditorPage from '../NoteEditorPage';

const noteFixture = {
  note_id: 'abc-123',
  title: 'The Nature of Mind',
  body: '# The Nature of Mind\n\nContent here.',
  tags: ['buddhism', 'mind'],
  note_type: 'permanent',
  status: 'active',
  created_at: '2026-01-01T00:00:00Z',
  updated_at: '2026-01-02T00:00:00Z',
  folder: 'Philosophy',
  source_url: null,
};

function makeQC() {
  return new QueryClient({ defaultOptions: { queries: { retry: false } } });
}

function Wrapper({ path = '/notes/abc-123' }: { path?: string }) {
  return (
    <QueryClientProvider client={makeQC()}>
      <MemoryRouter initialEntries={[path]}>
        <Routes>
          <Route path="/notes/new" element={<NoteEditorPage />} />
          <Route path="/notes/:id" element={<NoteEditorPage />} />
        </Routes>
      </MemoryRouter>
    </QueryClientProvider>
  );
}

describe('NoteEditorPage', () => {
  beforeEach(() => {
    vi.restoreAllMocks();
  });

  it('renders the editor after note loads', async () => {
    vi.spyOn(notesApi, 'getNote').mockResolvedValue(noteFixture as never);
    render(<Wrapper />);
    await waitFor(() => screen.getByTestId('note-editor'));
    expect(screen.getByTestId('note-editor')).toBeInTheDocument();
  });

  it('edit/preview toggle switches mode', async () => {
    vi.spyOn(notesApi, 'getNote').mockResolvedValue(noteFixture as never);
    render(<Wrapper />);
    await waitFor(() => screen.getByRole('button', { name: /preview/i }));
    fireEvent.click(screen.getByRole('button', { name: /preview/i }));
    await waitFor(() => screen.getByRole('button', { name: /edit/i }));
    expect(screen.getByRole('button', { name: /edit/i })).toBeInTheDocument();
  });

  it('renders blank editor for new note route', async () => {
    render(<Wrapper path="/notes/new" />);
    // Template gallery opens first — close it
    await waitFor(() => screen.getByRole('dialog'));
    fireEvent.click(screen.getByRole('button', { name: /close template gallery/i }));
    await waitFor(() => screen.getByTestId('note-editor'));
    expect(screen.getByTestId('note-editor')).toBeInTheDocument();
  });
});
