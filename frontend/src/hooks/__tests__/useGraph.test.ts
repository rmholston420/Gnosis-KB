/// <reference types="vitest/globals" />
import { renderHook, waitFor } from '@testing-library/react';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import React from 'react';
import { useGraphData, useFullGraph } from '../useGraph';
import api from '../../services/api';

vi.mock('../../services/api');

const sampleGraph = {
  nodes: [{ note_id: 'a', title: 'Alpha' }],
  edges: [],
};

const wrapper = ({ children }: { children: React.ReactNode }) =>
  React.createElement(QueryClientProvider, {
    client: new QueryClient({ defaultOptions: { queries: { retry: false } } }),
  }, children);

describe('useGraph hooks', () => {
  beforeEach(() => { vi.clearAllMocks(); });

  it('useGraphData (alias) and useFullGraph return graph data', async () => {
    (api.getGraph as ReturnType<typeof vi.fn>).mockResolvedValue(sampleGraph);

    const { result: r1 } = renderHook(() => useGraphData(),  { wrapper });
    const { result: r2 } = renderHook(() => useFullGraph(),  { wrapper });

    await waitFor(() => r1.current.isSuccess && r2.current.isSuccess);
    expect(r1.current.data?.nodes).toHaveLength(1);
    expect(r2.current.data?.nodes).toHaveLength(1);
  });
});
