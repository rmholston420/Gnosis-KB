import { describe, it, expect, vi } from 'vitest';
import { renderHook, waitFor } from '@testing-library/react';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { createElement } from 'react';
import { makeSearchResult } from '../../test/factories';

vi.mock('../../api/search', () => ({
  searchNotes: vi.fn(async () => ({
    query: 'zettelkasten',
    mode:  'hybrid',
    items: [makeSearchResult({ title: 'Zettelkasten Method' })],
    total: 1,
  })),
}));

import { useSearch } from '../useSearch';

function makeWrapper() {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return ({ children }: { children: React.ReactNode }) =>
    createElement(QueryClientProvider, { client: qc }, children);
}

describe('useSearch', () => {
  it('returns results for a query', async () => {
    const { result } = renderHook(() => useSearch('zettelkasten', 'hybrid'), { wrapper: makeWrapper() });
    await waitFor(() => expect(result.current.isSuccess).toBe(true));
    expect(result.current.data?.items[0].title).toBe('Zettelkasten Method');
  });

  it('is disabled when query is empty', () => {
    const { result } = renderHook(() => useSearch('', 'hybrid'), { wrapper: makeWrapper() });
    expect(result.current.isLoading).toBe(false);
    expect(result.current.data).toBeUndefined();
  });
});
