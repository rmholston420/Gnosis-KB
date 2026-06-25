/// <reference types="vitest/globals" />
import { renderHook, waitFor, act } from '@testing-library/react';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import React from 'react';
import { useNotes, useNotesList, useUpdateNote, useCreateNote, useDeleteNote } from '../useNotes';

const mockListNotes  = vi.fn();
const mockCreateNote = vi.fn();
const mockUpdateNote = vi.fn();
const mockDeleteNote = vi.fn();

vi.mock('../../services/api', () => ({
  default: {
    listNotes:  (...a: unknown[]) => mockListNotes(...a),
    createNote: (...a: unknown[]) => mockCreateNote(...a),
    updateNote: (...a: unknown[]) => mockUpdateNote(...a),
    deleteNote: (...a: unknown[]) => mockDeleteNote(...a),
    getNote:    vi.fn(),
  },
}));

// useNotes also imports getBacklinks from '../api/notes' — stub that module
vi.mock('../../api/notes', () => ({
  getBacklinks: vi.fn().mockResolvedValue({ backlinks: [] }),
  default: {},
}));

const note = {
  note_id: 'note-001', title: 'Test Note', body: '# Test',
  created_at: '2026-01-01T00:00:00Z', updated_at: '2026-01-01T00:00:00Z',
};

const wrapper = ({ children }: { children: React.ReactNode }) =>
  React.createElement(
    QueryClientProvider,
    {
      client: new QueryClient({
        defaultOptions: { queries: { retry: false }, mutations: { retry: false } },
      }),
    },
    children,
  );

describe('useNotes hooks', () => {
  beforeEach(() => { vi.clearAllMocks(); });

  it('useNotes and useNotesList alias fetch notes list', async () => {
    mockListNotes.mockResolvedValue([note]);
    const { result: r1 } = renderHook(() => useNotes(),     { wrapper });
    const { result: r2 } = renderHook(() => useNotesList(), { wrapper });
    // Wait for each hook independently — logical-AND short-circuits if r1 settles first
    await waitFor(() => expect(r1.current.isSuccess).toBe(true));
    await waitFor(() => expect(r2.current.isSuccess).toBe(true));
    expect(r1.current.data).toHaveLength(1);
    expect(r2.current.data).toHaveLength(1);
  });

  it('useUpdateNote mutates with { id, payload }', async () => {
    mockUpdateNote.mockResolvedValue({ ...note, title: 'Updated' });
    const { result } = renderHook(() => useUpdateNote(), { wrapper });
    await act(async () => {
      await result.current.mutateAsync({ id: 'note-001', payload: { title: 'Updated' } });
    });
    expect(mockUpdateNote).toHaveBeenCalledWith('note-001', { title: 'Updated' });
  });

  it('useUpdateNote also accepts a noteId arg (compat)', () => {
    const { result } = renderHook(() => useUpdateNote('note-001'), { wrapper });
    expect(typeof result.current.mutateAsync).toBe('function');
  });

  it('useCreateNote creates a note', async () => {
    mockCreateNote.mockResolvedValue(note);
    const { result } = renderHook(() => useCreateNote(), { wrapper });
    await act(async () => {
      await result.current.mutateAsync({ title: 'New', body: '' });
    });
    expect(mockCreateNote).toHaveBeenCalledWith({ title: 'New', body: '' });
  });

  it('useDeleteNote deletes a note', async () => {
    mockDeleteNote.mockResolvedValue(undefined);
    const { result } = renderHook(() => useDeleteNote(), { wrapper });
    await act(async () => { await result.current.mutateAsync('note-001'); });
    expect(mockDeleteNote).toHaveBeenCalledWith('note-001');
  });
});
