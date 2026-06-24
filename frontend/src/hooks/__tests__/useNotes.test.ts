import { describe, it, expect, vi, beforeEach } from 'vitest';
import { renderHook, waitFor } from '@testing-library/react';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { createElement } from 'react';
import { makeNote, makeListItem } from '../../test/factories';

// --- mock the api module ---
vi.mock('../../api/notes', () => ({
  fetchNotes:   vi.fn(async () => ({ items: [makeListItem()], total: 1, page: 1, limit: 20, pages: 1 })),
  fetchNote:    vi.fn(async () => makeNote()),
  createNote:   vi.fn(async () => makeNote({ note_id: 'new-001', title: 'New' })),
  updateNote:   vi.fn(async () => makeNote({ title: 'Updated' })),
  deleteNote:   vi.fn(async () => ({ ok: true })),
}));

import { useNotesList, useNote, useCreateNote, useUpdateNote, useDeleteNote } from '../useNotes';

function makeWrapper() {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return ({ children }: { children: React.ReactNode }) =>
    createElement(QueryClientProvider, { client: qc }, children);
}

describe('useNotesList', () => {
  it('returns notes from the API', async () => {
    const { result } = renderHook(() => useNotesList(), { wrapper: makeWrapper() });
    await waitFor(() => expect(result.current.isSuccess).toBe(true));
    expect(result.current.data?.items).toHaveLength(1);
  });
});

describe('useNote', () => {
  it('fetches a single note', async () => {
    const { result } = renderHook(() => useNote('note-001'), { wrapper: makeWrapper() });
    await waitFor(() => expect(result.current.isSuccess).toBe(true));
    expect(result.current.data?.note_id).toBe('note-001');
  });
});

describe('useCreateNote', () => {
  beforeEach(() => vi.clearAllMocks());
  it('mutation resolves with new note', async () => {
    const { result } = renderHook(() => useCreateNote(), { wrapper: makeWrapper() });
    await result.current.mutateAsync({ title: 'New', body: '' });
    await waitFor(() => expect(result.current.isSuccess).toBe(true));
  });
});

describe('useUpdateNote', () => {
  it('mutation resolves', async () => {
    const { result } = renderHook(() => useUpdateNote('note-001'), { wrapper: makeWrapper() });
    await result.current.mutateAsync({ title: 'Updated' });
    await waitFor(() => expect(result.current.isSuccess).toBe(true));
  });
});

describe('useDeleteNote', () => {
  it('mutation resolves', async () => {
    const { result } = renderHook(() => useDeleteNote(), { wrapper: makeWrapper() });
    await result.current.mutateAsync('note-001');
    await waitFor(() => expect(result.current.isSuccess).toBe(true));
  });
});
