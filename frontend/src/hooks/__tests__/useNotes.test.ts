/// <reference types="vitest/globals" />
import { renderHook, waitFor, act } from '@testing-library/react';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import React from 'react';
import { useNotes, useNotesList, useUpdateNote, useCreateNote, useDeleteNote } from '../useNotes';
import api from '../../services/api';

vi.mock('../../services/api');

const note = {
  note_id: 'note-001', title: 'Test Note', body: '# Test',
  created_at: '2026-01-01T00:00:00Z', updated_at: '2026-01-01T00:00:00Z',
};

const wrapper = ({ children }: { children: React.ReactNode }) =>
  React.createElement(QueryClientProvider, {
    client: new QueryClient({ defaultOptions: { queries: { retry: false }, mutations: { retry: false } } }),
  }, children);

describe('useNotes hooks', () => {
  beforeEach(() => { vi.clearAllMocks(); });

  it('useNotes and useNotesList alias fetch notes list', async () => {
    (api.listNotes as ReturnType<typeof vi.fn>).mockResolvedValue([note]);
    const { result: r1 } = renderHook(() => useNotes(),     { wrapper });
    const { result: r2 } = renderHook(() => useNotesList(), { wrapper });
    await waitFor(() => r1.current.isSuccess && r2.current.isSuccess);
    expect(r1.current.data).toHaveLength(1);
    expect(r2.current.data).toHaveLength(1);
  });

  it('useUpdateNote mutates with { id, payload }', async () => {
    (api.updateNote as ReturnType<typeof vi.fn>).mockResolvedValue({ ...note, title: 'Updated' });
    const { result } = renderHook(() => useUpdateNote(), { wrapper });
    await act(async () => {
      await result.current.mutateAsync({ id: 'note-001', payload: { title: 'Updated' } });
    });
    expect(api.updateNote).toHaveBeenCalledWith('note-001', { title: 'Updated' });
  });

  it('useUpdateNote also accepts a noteId arg (compat)', () => {
    // Calling with a string arg must not throw — it is ignored
    const { result } = renderHook(() => useUpdateNote('note-001'), { wrapper });
    expect(typeof result.current.mutateAsync).toBe('function');
  });

  it('useCreateNote creates a note', async () => {
    (api.createNote as ReturnType<typeof vi.fn>).mockResolvedValue(note);
    const { result } = renderHook(() => useCreateNote(), { wrapper });
    await act(async () => {
      await result.current.mutateAsync({ title: 'New', body: '' });
    });
    expect(api.createNote).toHaveBeenCalledWith({ title: 'New', body: '' });
  });

  it('useDeleteNote deletes a note', async () => {
    (api.deleteNote as ReturnType<typeof vi.fn>).mockResolvedValue(undefined);
    const { result } = renderHook(() => useDeleteNote(), { wrapper });
    await act(async () => { await result.current.mutateAsync('note-001'); });
    expect(api.deleteNote).toHaveBeenCalledWith('note-001');
  });
});
