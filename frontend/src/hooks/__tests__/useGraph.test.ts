import { describe, it, expect, vi } from 'vitest';
import { renderHook, waitFor } from '@testing-library/react';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { createElement } from 'react';

const mockStats = {
  total_notes: 42, total_links: 87, orphan_count: 3,
  avg_degree: 2.07, density: 0.05,
  most_connected: [{ note_id: 'x', degree: 12, title: 'Zettelkasten' }],
};
const mockGraph = {
  nodes: [{ note_id: 'a', title: 'A', incoming_link_count: 0, outgoing_link_count: 1 }],
  edges: [],
};

// Mock using the names that useGraph.ts resolves at runtime:
// getFullGraph  → used as fetchGraphData fallback
// getGraphStats → used as fetchGraphStats fallback
// We also provide the test-friendly aliases so both code paths work.
vi.mock('../../api/graph', () => ({
  getFullGraph:      vi.fn(async () => mockGraph),
  getGraphStats:     vi.fn(async () => mockStats),
  fetchGraphData:    vi.fn(async () => mockGraph),
  fetchGraphStats:   vi.fn(async () => mockStats),
  getNeighborhood:   vi.fn(async () => ({ nodes: [], edges: [] })),
  getClusters:       vi.fn(async () => ({ nodes: [], edges: [] })),
}));

import { useGraphData, useGraphStats } from '../useGraph';

function makeWrapper() {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return ({ children }: { children: React.ReactNode }) =>
    createElement(QueryClientProvider, { client: qc }, children);
}

describe('useGraphData', () => {
  it('returns graph nodes and edges', async () => {
    const { result } = renderHook(() => useGraphData(), { wrapper: makeWrapper() });
    await waitFor(() => expect(result.current.isSuccess).toBe(true));
    expect(result.current.data?.nodes).toHaveLength(1);
  });
});

describe('useGraphStats', () => {
  it('returns vault stats', async () => {
    const { result } = renderHook(() => useGraphStats(), { wrapper: makeWrapper() });
    await waitFor(() => expect(result.current.isSuccess).toBe(true));
    expect(result.current.data?.total_notes).toBe(42);
    expect(result.current.data?.orphan_count).toBe(3);
  });
});
