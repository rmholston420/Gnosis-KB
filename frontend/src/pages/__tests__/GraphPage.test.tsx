/**
 * GraphPage.test.tsx
 *
 * Strategy:
 * - react-force-graph-2d is lazy-loaded and uses canvas/WebGL — mock it
 *   with a simple div so jsdom never touches unavailable browser APIs.
 * - canvas.getContext is mocked to return null so the LightRAG canvas
 *   useEffect exits cleanly.
 * - react-router-dom navigate is mocked via vi.mock so node-click navigation
 *   can be asserted without a real router.
 * - @tanstack/react-query is used directly (no mock) — axios responses are
 *   stubbed via vi.hoisted.
 */
import React from 'react';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import { describe, it, expect, vi, beforeEach } from 'vitest';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { MemoryRouter } from 'react-router-dom';

// ---------------------------------------------------------------------------
// Hoist axios stubs
// ---------------------------------------------------------------------------
const { mockGet, mockPost } = vi.hoisted(() => ({
  mockGet:  vi.fn(),
  mockPost: vi.fn(),
}));

vi.mock('axios', () => ({
  default: { get: mockGet, post: mockPost, delete: vi.fn(), create: vi.fn(() => ({ get: mockGet, post: mockPost })) },
}));

// Mock react-force-graph-2d (lazy) — just render a stub canvas placeholder
vi.mock('react-force-graph-2d', () => ({
  default: vi.fn(({ graphData }: { graphData: { nodes: unknown[] } }) =>
    React.createElement('div', { 'data-testid': 'force-graph' },
      `nodes:${graphData.nodes.length}`
    )
  ),
}));

// Suppress canvas getContext so useEffect exits without crashing
Object.defineProperty(HTMLCanvasElement.prototype, 'getContext', {
  value: () => null,
  configurable: true,
});

import GraphPage from '../GraphPage';

const GRAPH_DATA = {
  nodes: [
    { id: 'n1', title: 'EEG Note',    note_type: 'zettel',  status: 'draft',    folder: '10-zettelkasten', incoming_link_count: 1, outgoing_link_count: 2 },
    { id: 'n2', title: 'BCI Project', note_type: 'project', status: 'evergreen', folder: '20-projects',      incoming_link_count: 0, outgoing_link_count: 1 },
  ],
  edges: [
    { source: 'n1', target: 'n2', link_text: 'see also' },
  ],
};

const ENTITIES: { id: string; label: string; cluster: number }[] = [
  { id: 'EEG',      label: 'EEG Signals', cluster: 0 },
  { id: 'LightRAG', label: 'LightRAG',    cluster: 1 },
];

function wrap() {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(
    <QueryClientProvider client={qc}>
      <MemoryRouter>
        <GraphPage />
      </MemoryRouter>
    </QueryClientProvider>
  );
}

beforeEach(() => {
  vi.resetAllMocks();
  // Default: graph data loaded, entities empty
  mockGet.mockImplementation((url: string) => {
    if (url.includes('/graph/entities')) return Promise.resolve({ data: ENTITIES });
    if (url.includes('/graph'))          return Promise.resolve({ data: GRAPH_DATA });
    return Promise.resolve({ data: [] });
  });
  mockPost.mockResolvedValue({ data: {} });
});

describe('GraphPage — render & tabs', () => {
  it('renders page heading', async () => {
    wrap();
    expect(screen.getByText(/knowledge graph/i)).toBeInTheDocument();
  });

  it('renders Wikilinks tab active by default', () => {
    wrap();
    expect(screen.getByRole('button', { name: /wikilinks/i })).toBeInTheDocument();
  });

  it('renders LightRAG Knowledge tab button', () => {
    wrap();
    expect(screen.getByRole('button', { name: /lightrag knowledge/i })).toBeInTheDocument();
  });

  it('renders Refresh button', () => {
    wrap();
    expect(screen.getByRole('button', { name: /refresh/i })).toBeInTheDocument();
  });
});

describe('GraphPage — wikilinks tab', () => {
  it('shows the ForceGraph when nodes are loaded', async () => {
    wrap();
    await waitFor(() =>
      expect(screen.getByTestId('force-graph')).toBeInTheDocument()
    );
  });

  it('shows node count badge after data loads', async () => {
    wrap();
    await waitFor(() =>
      expect(screen.getByText(/2 nodes/)).toBeInTheDocument()
    );
  });

  it('filters nodes via search input', async () => {
    wrap();
    await waitFor(() => screen.getByTestId('force-graph'));
    const searchInput = screen.getAllByPlaceholderText(/filter nodes/i)[0];
    fireEvent.change(searchInput, { target: { value: 'EEG' } });
    await waitFor(() =>
      expect(screen.getByTestId('force-graph').textContent).toContain('nodes:1')
    );
  });

  it('shows empty state with Sync Vault button when no nodes', async () => {
    mockGet.mockImplementation((url: string) => {
      if (url.includes('/graph')) return Promise.resolve({ data: { nodes: [], edges: [] } });
      return Promise.resolve({ data: [] });
    });
    wrap();
    await waitFor(() =>
      expect(screen.getByRole('button', { name: /sync vault/i })).toBeInTheDocument()
    );
  });
});

describe('GraphPage — LightRAG tab', () => {
  it('switches to LightRAG tab on click', async () => {
    wrap();
    fireEvent.click(screen.getByRole('button', { name: /lightrag knowledge/i }));
    await waitFor(() =>
      expect(screen.getByText(/entities/i)).toBeInTheDocument()
    );
  });

  it('shows entity list after switching to LightRAG tab', async () => {
    // entities endpoint returns data when tab is active
    mockGet.mockImplementation((url: string) => {
      if (url.includes('/graph/entities') && !url.includes('relations')) return Promise.resolve({ data: ENTITIES });
      if (url.includes('/graph/lightrag')) return Promise.resolve({ data: { entities: [], relations: [] } });
      if (url.includes('/graph'))          return Promise.resolve({ data: GRAPH_DATA });
      return Promise.resolve({ data: [] });
    });
    wrap();
    fireEvent.click(screen.getByRole('button', { name: /lightrag knowledge/i }));
    await waitFor(() => screen.getByText(/entities/i));
    await waitFor(() =>
      expect(screen.getByText('EEG')).toBeInTheDocument()
    );
  });

  it('filters entity list by search', async () => {
    mockGet.mockImplementation((url: string) => {
      if (url.includes('/graph/entities') && !url.includes('relations')) return Promise.resolve({ data: ENTITIES });
      if (url.includes('/graph/lightrag')) return Promise.resolve({ data: { entities: [], relations: [] } });
      if (url.includes('/graph'))          return Promise.resolve({ data: GRAPH_DATA });
      return Promise.resolve({ data: [] });
    });
    wrap();
    fireEvent.click(screen.getByRole('button', { name: /lightrag knowledge/i }));
    await waitFor(() => screen.getByText('EEG'));
    const entitySearchInput = screen.getByPlaceholderText(/filter entities/i);
    fireEvent.change(entitySearchInput, { target: { value: 'LightRAG' } });
    await waitFor(() =>
      expect(screen.queryByText('EEG')).not.toBeInTheDocument()
    );
    expect(screen.getByText('LightRAG')).toBeInTheDocument();
  });

  it('shows LightRAG graph not available when lrGraphData is null', async () => {
    mockGet.mockImplementation((url: string) => {
      if (url.includes('/graph/entities') && !url.includes('relations')) return Promise.resolve({ data: [] });
      if (url.includes('/graph/lightrag')) return Promise.reject(new Error('not found'));
      if (url.includes('/graph'))          return Promise.resolve({ data: GRAPH_DATA });
      return Promise.resolve({ data: [] });
    });
    wrap();
    fireEvent.click(screen.getByRole('button', { name: /lightrag knowledge/i }));
    await waitFor(() =>
      expect(screen.getByText(/LightRAG graph not available/i)).toBeInTheDocument()
    );
  });
});
