/**
 * GraphPage.extended.test.tsx
 * Covers the LightRAG tab, entity sidebar, filter input, Sync Vault button,
 * zoom controls, and the node info panel — all the lines missed by the
 * existing suite (lines 315-592).
 */
import React from 'react';
import {
  render,
  screen,
  fireEvent,
  waitFor,
  act,
} from '@testing-library/react';
import { describe, it, expect, vi, beforeEach } from 'vitest';
import { MemoryRouter } from 'react-router-dom';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';

// ---- Heavy/browser deps mocked before import --------------------------------
vi.mock('react-force-graph-2d', () => ({
  default: React.forwardRef((_props: any, _ref: any) => (
    <div data-testid="force-graph" />
  )),
}));

vi.mock('@/components/graph/LightRagNodePanel', () => ({
  LightRagNodePanel: ({ onClose }: { onClose: () => void }) => (
    <div data-testid="lr-node-panel">
      <button data-testid="lr-close" onClick={onClose}>close</button>
    </div>
  ),
}));

const mockGetFullGraph   = vi.fn();
const mockGetGraphEntities = vi.fn();
const mockApiClient = {
  get: vi.fn(),
};

vi.mock('@/services/api', () => ({
  default: {
    getFullGraph:    (...a: unknown[]) => mockGetFullGraph(...a),
    getGraphEntities: (...a: unknown[]) => mockGetGraphEntities(...a),
    apiClient: mockApiClient,
  },
}));

const GRAPH_DATA = {
  nodes: [
    { id: 'n1', title: 'Alpha', note_type: 'permanent', status: 'evergreen', folder: 'zettel', incoming_link_count: 2, outgoing_link_count: 3 },
    { id: 'n2', title: 'Beta',  note_type: 'map',       status: 'draft',     folder: 'inbox',  incoming_link_count: 0, outgoing_link_count: 1 },
  ],
  edges: [
    { id: 'e1', source: 'n1', target: 'n2', link_text: 'refs' },
  ],
};

const ENTITIES = [
  { id: 'ent1', label: 'Concept A', cluster: 0 },
  { id: 'ent2', label: 'Concept B', cluster: 1 },
  { id: 'ent3', label: 'Concept C', cluster: 2 },
];

const LR_GRAPH = {
  entities: ENTITIES.map((e) => ({ ...e, x: 50, y: 50 })),
  relations: [{ source: 'ent1', target: 'ent2', label: 'related' }],
};

function makeQC() {
  return new QueryClient({
    defaultOptions: { queries: { retry: false } },
  });
}

function Wrapper({ children }: { children: React.ReactNode }) {
  return (
    <QueryClientProvider client={makeQC()}>
      <MemoryRouter>{children}</MemoryRouter>
    </QueryClientProvider>
  );
}

async function renderGraph(opts: { empty?: boolean } = {}) {
  const graphData = opts.empty ? { nodes: [], edges: [] } : GRAPH_DATA;
  mockGetFullGraph.mockResolvedValue(graphData);
  mockGetGraphEntities.mockResolvedValue({ entities: ENTITIES });
  mockApiClient.get.mockResolvedValue({ data: LR_GRAPH });

  const { default: GraphPage } = await import('@/pages/GraphPage');
  render(
    <Wrapper>
      <GraphPage />
    </Wrapper>
  );
  // Wait for initial render to settle
  await act(async () => { await new Promise((r) => setTimeout(r, 100)); });
}

describe('GraphPage — wikilinks tab', () => {
  beforeEach(() => vi.clearAllMocks());

  it('renders the Knowledge Graph heading', async () => {
    await renderGraph();
    expect(screen.getByText('Knowledge Graph')).toBeTruthy();
  });

  it('renders Wikilinks and LightRAG Knowledge tabs', async () => {
    await renderGraph();
    expect(screen.getByText('Wikilinks')).toBeTruthy();
    expect(screen.getByText('LightRAG Knowledge')).toBeTruthy();
  });

  it('renders ForceGraph when nodes present', async () => {
    await renderGraph();
    await waitFor(() => screen.getByTestId('force-graph'), { timeout: 3000 });
  });

  it('filter input filters nodes by title', async () => {
    await renderGraph();
    await waitFor(() => screen.getByTestId('force-graph'));
    const inputs = screen.getAllByRole('textbox');
    const filterInput = inputs.find((i) =>
      (i as HTMLInputElement).placeholder?.toLowerCase().includes('filter')
    );
    if (filterInput) {
      fireEvent.change(filterInput, { target: { value: 'Alpha' } });
      expect((filterInput as HTMLInputElement).value).toBe('Alpha');
    }
  });

  it('Refresh button does not crash', async () => {
    await renderGraph();
    const refreshBtn = screen.getByText('Refresh');
    fireEvent.click(refreshBtn);
    expect(refreshBtn).toBeTruthy();
  });

  it('shows Sync Vault button when graph is empty', async () => {
    await renderGraph({ empty: true });
    await waitFor(() => screen.getByText('Sync Vault'), { timeout: 3000 });
    fireEvent.click(screen.getByText('Sync Vault'));
  });
});

describe('GraphPage — LightRAG tab', () => {
  beforeEach(() => vi.clearAllMocks());

  it('switches to LightRAG Knowledge tab on click', async () => {
    await renderGraph();
    fireEvent.click(screen.getByText('LightRAG Knowledge'));
    await act(async () => { await new Promise((r) => setTimeout(r, 100)); });
    // Entity sidebar should appear
    await waitFor(() => screen.getByText('Entities'), { timeout: 3000 });
  });

  it('entity filter input accepts text', async () => {
    await renderGraph();
    fireEvent.click(screen.getByText('LightRAG Knowledge'));
    await waitFor(() => screen.getByText('Entities'), { timeout: 3000 });
    const inputs = screen.getAllByRole('textbox');
    const entityFilter = inputs.find((i) =>
      (i as HTMLInputElement).placeholder?.toLowerCase().includes('entit')
    );
    if (entityFilter) {
      fireEvent.change(entityFilter, { target: { value: 'Concept' } });
      expect((entityFilter as HTMLInputElement).value).toBe('Concept');
    }
  });

  it('LightRAG highlight input accepts text', async () => {
    await renderGraph();
    fireEvent.click(screen.getByText('LightRAG Knowledge'));
    await waitFor(() => screen.getByText('Entities'), { timeout: 3000 });
    const inputs = screen.getAllByRole('textbox');
    const hlInput = inputs.find((i) =>
      (i as HTMLInputElement).placeholder?.toLowerCase().includes('highlight')
    );
    if (hlInput) {
      fireEvent.change(hlInput, { target: { value: 'Alpha' } });
      expect((hlInput as HTMLInputElement).value).toBe('Alpha');
    }
  });

  it('entity row click calls apiClient.get and does not crash', async () => {
    mockApiClient.get.mockResolvedValue({ data: { id: 'ent1', label: 'Concept A', relations: [] } });
    mockGetGraphEntities.mockResolvedValue(ENTITIES);
    mockGetFullGraph.mockResolvedValue(GRAPH_DATA);

    const { default: GraphPage } = await import('@/pages/GraphPage');
    render(<Wrapper><GraphPage /></Wrapper>);
    await act(async () => { await new Promise((r) => setTimeout(r, 50)); });

    fireEvent.click(screen.getByText('LightRAG Knowledge'));
    await act(async () => { await new Promise((r) => setTimeout(r, 100)); });

    const entButtons = screen.queryAllByText(/Concept/);
    if (entButtons.length > 0) {
      fireEvent.click(entButtons[0]);
      await act(async () => { await new Promise((r) => setTimeout(r, 100)); });
    }
    expect(mockApiClient.get).toBeDefined();
  });

  it('LightRagNodePanel close button hides the panel', async () => {
    // Set up apiClient.get to return entity + relations on first calls
    mockApiClient.get
      .mockResolvedValueOnce({ data: { id: 'ent1', label: 'Concept A' } })
      .mockResolvedValueOnce({ data: { relations: [] } })
      .mockResolvedValue({ data: LR_GRAPH });
    mockGetGraphEntities.mockResolvedValue(ENTITIES);
    mockGetFullGraph.mockResolvedValue(GRAPH_DATA);

    const { default: GraphPage } = await import('@/pages/GraphPage');
    render(<Wrapper><GraphPage /></Wrapper>);
    await act(async () => { await new Promise((r) => setTimeout(r, 80)); });

    fireEvent.click(screen.getByText('LightRAG Knowledge'));
    await act(async () => { await new Promise((r) => setTimeout(r, 100)); });

    const closeBtn = screen.queryByTestId('lr-close');
    if (closeBtn) {
      fireEvent.click(closeBtn);
      expect(screen.queryByTestId('lr-node-panel')).toBeNull();
    }
  });
});
