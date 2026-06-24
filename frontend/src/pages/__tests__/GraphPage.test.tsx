/**
 * GraphPage.test.tsx
 *
 * Strategy:
 * - react-force-graph-2d is lazy-loaded and uses canvas/WebGL — mock it
 *   with a simple div so jsdom never touches unavailable browser APIs.
 * - canvas.getContext is mocked to return null so the LightRAG canvas
 *   useEffect exits cleanly.
 * - api.ts uses native fetch() throughout (NOT axios). All network stubs
 *   use vi.stubGlobal('fetch', ...) intercepting by URL pathname.
 * - react-router-dom navigate is mocked via vi.mock so node-click
 *   navigation can be asserted without a real router.
 */
import React from 'react';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { MemoryRouter } from 'react-router-dom';

// ---------------------------------------------------------------------------
// Mock react-force-graph-2d (lazy) — render a stub so jsdom never hits WebGL
// ---------------------------------------------------------------------------
vi.mock('react-force-graph-2d', () => ({
  default: vi.fn(({ graphData }: { graphData: { nodes: unknown[] } }) =>
    React.createElement('div', { 'data-testid': 'force-graph' },
      `nodes:${graphData.nodes.length}`
    )
  ),
}));

// Suppress canvas getContext so LightRAG useEffect exits without crashing
Object.defineProperty(HTMLCanvasElement.prototype, 'getContext', {
  value: () => null,
  configurable: true,
});

// ---------------------------------------------------------------------------
// Test data
// ---------------------------------------------------------------------------
const GRAPH_DATA = {
  nodes: [
    { id: 'n1', title: 'EEG Note',    note_type: 'zettel',  status: 'draft',     folder: '10-zettelkasten', incoming_link_count: 1, outgoing_link_count: 2 },
    { id: 'n2', title: 'BCI Project', note_type: 'project', status: 'evergreen', folder: '20-projects',      incoming_link_count: 0, outgoing_link_count: 1 },
  ],
  edges: [
    { source: 'n1', target: 'n2', link_text: 'see also' },
  ],
};

const LR_GRAPH_DATA = { entities: [], relations: [] };

const ENTITIES = [
  { id: 'EEG',      label: 'EEG Signals', cluster: 0 },
  { id: 'LightRAG', label: 'LightRAG',    cluster: 1 },
];

// ---------------------------------------------------------------------------
// fetch mock helpers
// ---------------------------------------------------------------------------

/** Build a minimal Response-like object that satisfies the api.ts fetch usage. */
function makeResponse(body: unknown, ok = true, status = 200): Response {
  const json = JSON.stringify(body);
  return {
    ok,
    status,
    statusText: ok ? 'OK' : 'Error',
    json: () => Promise.resolve(body),
    text: () => Promise.resolve(json),
    clone: function () { return this; },
  } as unknown as Response;
}

/**
 * Default fetch stub: routes by URL.pathname segment.
 * - /api/v1/graph/entities  → { entities: ENTITIES }
 * - /api/v1/graph/lightrag  → LR_GRAPH_DATA
 * - /api/v1/graph/          → GRAPH_DATA
 * - everything else         → {}
 */
function makeDefaultFetch(overrides: Record<string, unknown> = {}) {
  return vi.fn((input: RequestInfo | URL) => {
    const url = typeof input === 'string' ? input : input instanceof URL ? input.href : (input as Request).url;

    for (const [pattern, data] of Object.entries(overrides)) {
      if (url.includes(pattern)) return Promise.resolve(makeResponse(data));
    }

    if (url.includes('/graph/entities')) return Promise.resolve(makeResponse({ entities: ENTITIES }));
    if (url.includes('/graph/lightrag'))  return Promise.resolve(makeResponse(LR_GRAPH_DATA));
    if (url.includes('/graph'))           return Promise.resolve(makeResponse(GRAPH_DATA));
    return Promise.resolve(makeResponse({}));
  });
}

// ---------------------------------------------------------------------------
// Import component AFTER mocks are set up
// ---------------------------------------------------------------------------
import GraphPage from '../GraphPage';

// ---------------------------------------------------------------------------
// Wrapper
// ---------------------------------------------------------------------------
function wrap() {
  // Fresh QueryClient per test so cache never bleeds between tests
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
  vi.stubGlobal('fetch', makeDefaultFetch());
  // Suppress "localStorage is not available" noise from api.ts in jsdom
  vi.spyOn(Storage.prototype, 'getItem').mockReturnValue(null);
});

afterEach(() => {
  vi.unstubAllGlobals();
  vi.restoreAllMocks();
});

// ---------------------------------------------------------------------------
// Tests
// ---------------------------------------------------------------------------

describe('GraphPage — render & tabs', () => {
  it('renders page heading', () => {
    wrap();
    expect(screen.getByText(/knowledge graph/i)).toBeInTheDocument();
  });

  it('renders Wikilinks tab button', () => {
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

  it('shows Sync Vault button when no nodes', async () => {
    vi.stubGlobal('fetch', makeDefaultFetch({
      '/graph/': { nodes: [], edges: [] },
      '/graph':  { nodes: [], edges: [] },
    }));
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
    wrap();
    fireEvent.click(screen.getByRole('button', { name: /lightrag knowledge/i }));
    await waitFor(() =>
      expect(screen.getByText('EEG')).toBeInTheDocument()
    );
    expect(screen.getByText('LightRAG')).toBeInTheDocument();
  });

  it('filters entity list by search', async () => {
    wrap();
    fireEvent.click(screen.getByRole('button', { name: /lightrag knowledge/i }));
    // Wait for both entities to appear
    await waitFor(() => screen.getByText('EEG'));
    // Now filter to only LightRAG
    const entitySearchInput = screen.getByPlaceholderText(/filter entities/i);
    fireEvent.change(entitySearchInput, { target: { value: 'LightRAG' } });
    await waitFor(() =>
      expect(screen.queryByText('EEG')).not.toBeInTheDocument()
    );
    expect(screen.getByText('LightRAG')).toBeInTheDocument();
  });

  it('shows LightRAG graph not available when lightrag endpoint fails', async () => {
    vi.stubGlobal('fetch', makeDefaultFetch({
      '/graph/lightrag': null, // will be overridden below
    }));
    // Override fetch to reject for lightrag
    vi.stubGlobal('fetch', vi.fn((input: RequestInfo | URL) => {
      const url = typeof input === 'string' ? input : input instanceof URL ? input.href : (input as Request).url;
      if (url.includes('/graph/entities')) return Promise.resolve(makeResponse({ entities: [] }));
      if (url.includes('/graph/lightrag'))  return Promise.resolve(makeResponse({}, false, 500));
      if (url.includes('/graph'))           return Promise.resolve(makeResponse(GRAPH_DATA));
      return Promise.resolve(makeResponse({}));
    }));
    wrap();
    fireEvent.click(screen.getByRole('button', { name: /lightrag knowledge/i }));
    await waitFor(() =>
      expect(screen.getByText(/LightRAG graph not available/i)).toBeInTheDocument()
    );
  });
});
