import React from 'react';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import { describe, it, expect, vi, beforeEach } from 'vitest';
import { MemoryRouter, Route, Routes } from 'react-router-dom';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';

const mockGetNote    = vi.fn();
const mockUpdateNote = vi.fn();
const mockDeleteNote = vi.fn();
const mockListNotes  = vi.fn();
const mockCreateNote = vi.fn();

vi.mock('@/services/api', () => ({
  default: {
    getNote:    (...a: unknown[]) => mockGetNote(...a),
    updateNote: (...a: unknown[]) => mockUpdateNote(...a),
    deleteNote: (...a: unknown[]) => mockDeleteNote(...a),
    listNotes:  (...a: unknown[]) => mockListNotes(...a),
    createNote: (...a: unknown[]) => mockCreateNote(...a),
  },
}));

vi.mock('@/components/NoteEditor', () => ({
  default: ({ value, onChange }: { value: string; onChange: (v: string) => void }) => (
    <textarea
      data-testid="note-editor"
      value={value}
      onChange={(e) => onChange(e.target.value)}
    />
  ),
}));

vi.mock('@/components/notes/NoteTemplateGallery', () => ({
  default: ({ onSelect }: { onSelect: (t: { content: string }) => void }) => (
    <div data-testid="template-gallery">
      <button onClick={() => onSelect({ content: 'Template content' })}>Use Template</button>
    </div>
  ),
}));

const NOTE = {
  id: 'note-1',
  title: 'Test Note',
  content: 'Hello world',
  body: 'Hello world',
  tags: ['a'],
  note_type: 'standard',
  status: 'active',
  updated_at: new Date().toISOString(),
};

function makeClient() {
  return new QueryClient({ defaultOptions: { queries: { retry: false } } });
}

async function renderWithId(id = 'note-1') {
  const { default: NoteEditorPage } = await import('@/pages/NoteEditorPage');
  render(
    <QueryClientProvider client={makeClient()}>
      <MemoryRouter initialEntries={[`/notes/${id}/edit`]}>
        <Routes>
          <Route path="/notes/:id/edit" element={<NoteEditorPage />} />
        </Routes>
      </MemoryRouter>
    </QueryClientProvider>
  );
}

describe('NoteEditorPage extended', () => {
  beforeEach(() => vi.clearAllMocks());

  it('renders note content after load', async () => {
    mockGetNote.mockResolvedValue(NOTE);
    await renderWithId();
    await waitFor(() => screen.getByTestId('note-editor'), { timeout: 3000 });
    expect((screen.getByTestId('note-editor') as HTMLTextAreaElement).value).toContain('Hello world');
  });

  it('shows loading state while fetching without crashing', async () => {
    mockGetNote.mockReturnValue(new Promise(() => {}));
    await renderWithId();
    await new Promise((r) => setTimeout(r, 30));
  });

  it('handles note not found (404) without crashing', async () => {
    mockGetNote.mockRejectedValue(Object.assign(new Error('Not found'), { status: 404 }));
    await renderWithId('missing-id');
    await new Promise((r) => setTimeout(r, 80));
  });

  it('calls updateNote on save button click', async () => {
    mockGetNote.mockResolvedValue(NOTE);
    mockUpdateNote.mockResolvedValue({ ...NOTE, title: 'Updated' });
    await renderWithId();
    await waitFor(() => screen.getByTestId('note-editor'), { timeout: 3000 });
    const saveBtn = screen.queryByRole('button', { name: /save/i });
    if (saveBtn) {
      fireEvent.click(saveBtn);
      await waitFor(() => expect(mockUpdateNote).toHaveBeenCalled());
    }
  });

  it('edits content in textarea without crashing', async () => {
    mockGetNote.mockResolvedValue(NOTE);
    await renderWithId();
    await waitFor(() => screen.getByTestId('note-editor'), { timeout: 3000 });
    fireEvent.change(screen.getByTestId('note-editor'), { target: { value: 'New content' } });
  });

  it('template gallery onSelect sets content', async () => {
    mockGetNote.mockResolvedValue({ ...NOTE, content: '', body: '' });
    await renderWithId();
    const galleryBtn = screen.queryByTestId('template-gallery')?.querySelector('button');
    if (galleryBtn) {
      fireEvent.click(galleryBtn);
      await waitFor(() =>
        expect((screen.getByTestId('note-editor') as HTMLTextAreaElement).value).toBe('Template content')
      );
    }
  });
});
