/**
 * GraphPage.extended.test.tsx
 * Covers node info panel, onNodeClick/onNodeHover, Sync Vault empty state,
 * LightRAG tab switch, entity sidebar search, entity row click (handleLrNodeClick).
 * Uncovered lines: 298-309, 315-317, 427-430, 441-471, 586-592
 */
import React from 'react';
import { render, screen, fireEvent, waitFor, act } from '@testing-library/react';
import { describe, it, expect, vi, beforeEach } from 'vitest';
import { MemoryRouter } from 'react-router-dom';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';

// ---- Mocks ----------------------------------------------------------------
const mockNavigate = vi.fn();
vi.mock('react-router-dom', async (orig) => {
  const actual = await orig<typeof import('react-router-dom')>();
  return { ...actual, useNavigate: () => mockNavigate };
});

const mockGetFullGraph      = vi.fn();
const mockGetGraphEntities  = vi.fn();
const mockSyncVault         = vi.fn();
const mockApiClient         = { get: vi.fn() };

vi.mock('@/services/api', () => ({
  default: {
    getFullGraph:     (...a: unknown[]) => mockGetFullGraph(...a),
    getGraphEntities: (...a: unknown[]) => mockGetGraphEntities(...a),
    syncVault:        (...a: unknown[]) => mockSyncVault(...a),
    apiClient:        mockApiClient,
  },
}));

// ForceGraph2D is a heavy canvas dep — stub it out and expose callbacks
vi.mock('react-force-graph-2d', () => ({
  default: vi.fn(({ onNodeClick, onNodeHover }: any) => {
    React.useEffect(() => {
      (window as any).__fgOnNodeClick = onNodeClick;
      (window as any).__fgOnNodeHover = onNodeHover;
    });
    return React.createElement('div', { 'data-testid': 'force-graph' });
  }),
}));

vi.mock('@/components/graph/LightRagNodePanel', () => ({
  LightRagNodePanel: ({ entity, onClose }: any) =>
    React.createElement(
      'div',
      { 'data-testid': 'lr-panel' },
      React.createElement('span', null, entity.id),
      React.createElement('button', { onClick: onClose }, 'Close Panel'),
    ),
}));

// Static import — must come AFTER all vi.mock() declarations so hoisting works
import GraphPage from '@/pages/GraphPage';

// ---------------------------------------------------------------------------

const GRAPH_DATA = {
  nodes: [
    { id: 'n1', title: 'Dharma', note_type: 'permanent', status: 'evergreen',
      folder: '10-dharma', incoming_link_count: 3, outgoing_link_count: 2 },
    { id: 'n2', title: 'Sangha', note_type: 'fleeting',  status: 'seedling',
      folder: '20-sangha', incoming_link_count: 1, outgoing_link_count: 1 },
  ],
  edges: [{ source: 'n1', target: 'n2', link_text: 'supports' }],
};

const ENTITIES = [
  { id: 'buddha', label: 'Buddha', cluster: 0 },
  { id: 'dharma', label: 'Dharma', cluster: 1 },
  { id: 'sangha', label: 'Sangha', cluster: 2 },
];

function makeClient() {
  return new QueryClient({
    defaultOptions: { queries: { retry: false, gcTime: 0 } },
  });
}

function renderPage(client?: QueryClient) {
  const qc = client ?? makeClient();
  return render(
    <QueryClientProvider client={qc}>
      <MemoryRouter>
        <React.Suspense fallback={<div>loading</div>}>
          <GraphPage />
        </React.Suspense>
      </MemoryRouter>
    </QueryClientProvider>
  );
}

describe('GraphPage', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    mockNavigate.mockClear();
    mockGetFullGraph.mockResolvedValue(GRAPH_DATA);
    mockGetGraphEntities.mockResolvedValue(ENTITIES);
    mockSyncVault.mockResolvedValue(undefined);
    mockApiClient.get.mockResolvedValue({ data: { id: 'e1', relations: [] } });
  });

  it('renders Knowledge Graph heading', async () => {
    renderPage();
    await waitFor(() =>
      expect(screen.getByText('Knowledge Graph')).toBeTruthy()
    );
  });

  it('renders Wikilinks and LightRAG tab buttons', async () => {
    renderPage();
    await waitFor(() => {
      expect(screen.getByText('Wikilinks')).toBeTruthy();
      expect(screen.getByText('LightRAG Knowledge')).toBeTruthy();
    });
  });

  it('renders node count badge when graph loads', async () => {
    renderPage();
    await waitFor(() =>
      expect(screen.getByText(/2 nodes/)).toBeTruthy()
    );
  });

  it('node info panel appears when onNodeHover is called', async () => {
    renderPage();
    await waitFor(() => screen.getByTestId('force-graph'));
    act(() => { (window as any).__fgOnNodeHover?.(GRAPH_DATA.nodes[0]); });
    await waitFor(() =>
      expect(screen.getByText('Dharma')).toBeTruthy()
    );
  });

  it('onNodeClick navigates to /notes/:id', async () => {
    renderPage();
    await waitFor(() => screen.getByTestId('force-graph'));
    act(() => { (window as any).__fgOnNodeClick?.(GRAPH_DATA.nodes[0]); });
    await waitFor(() =>
      expect(mockNavigate).toHaveBeenCalledWith('/notes/n1')
    );
  });

  it('node info panel close button clears panel', async () => {
    renderPage();
    await waitFor(() => screen.getByTestId('force-graph'));
    act(() => { (window as any).__fgOnNodeHover?.(GRAPH_DATA.nodes[0]); });
    await waitFor(() => screen.getByText('Dharma'));
    fireEvent.click(screen.getByText('\u2715'));
    await waitFor(() =>
      expect(screen.queryByText('Open Note')).toBeNull()
    );
  });

  it('Sync Vault button is shown in empty state', async () => {
    mockGetFullGraph.mockResolvedValue({ nodes: [], edges: [] });
    renderPage();
    await waitFor(() =>
      expect(screen.getByText('Sync Vault')).toBeTruthy()
    );
  });

  it('clicking Sync Vault calls syncVault mutation', async () => {
    mockGetFullGraph.mockResolvedValue({ nodes: [], edges: [] });
    renderPage();
    await waitFor(() => screen.getByText('Sync Vault'));
    fireEvent.click(screen.getByText('Sync Vault'));
    await waitFor(() => expect(mockSyncVault).toHaveBeenCalled());
  });

  it('switching to LightRAG tab shows entity sidebar heading', async () => {
    renderPage();
    await waitFor(() => screen.getByText('LightRAG Knowledge'));
    fireEvent.click(screen.getByText('LightRAG Knowledge'));
    await waitFor(() =>
      expect(screen.getByText('Entities')).toBeTruthy()
    );
  });

  it('entity sidebar shows entities after LightRAG tab switch', async () => {
    mockApiClient.get.mockResolvedValue({ data: null });
    renderPage();
    await waitFor(() => screen.getByText('LightRAG Knowledge'));
    fireEvent.click(screen.getByText('LightRAG Knowledge'));
    await waitFor(() => {
      expect(screen.getByText('buddha')).toBeTruthy();
      expect(screen.getByText('dharma')).toBeTruthy();
    });
  });

  it('entity search filter narrows entity list', async () => {
    mockApiClient.get.mockResolvedValue({ data: null });
    renderPage();
    fireEvent.click(screen.getByText('LightRAG Knowledge'));
    await waitFor(() => screen.getByText('buddha'));
    fireEvent.change(
      screen.getByPlaceholderText(/Filter entities/i),
      { target: { value: 'dharma' } }
    );
    await waitFor(() => {
      expect(screen.queryByText('buddha')).toBeNull();
      expect(screen.getByText('dharma')).toBeTruthy();
    });
  });

  it('clicking entity row calls handleLrNodeClick (apiClient.get)', async () => {
    mockApiClient.get
      .mockResolvedValueOnce({ data: null })
      .mockResolvedValueOnce({ data: { id: 'buddha', label: 'Buddha', cluster: 0 } })
      .mockResolvedValueOnce({ data: { relations: [] } });
    renderPage();
    fireEvent.click(screen.getByText('LightRAG Knowledge'));
    await waitFor(() => screen.getByText('buddha'));
    fireEvent.click(screen.getByText('buddha').closest('button')!);
    await waitFor(() =>
      expect(mockApiClient.get).toHaveBeenCalledWith(
        expect.stringContaining('/api/v1/graph/entities/buddha')
      )
    );
  });

  it('LightRagNodePanel renders when entity is selected and closes on button click', async () => {
    mockApiClient.get
      .mockResolvedValueOnce({ data: null })
      .mockResolvedValueOnce({ data: { id: 'buddha', label: 'Buddha', cluster: 0 } })
      .mockResolvedValueOnce({ data: { relations: [] } });
    renderPage();
    fireEvent.click(screen.getByText('LightRAG Knowledge'));
    await waitFor(() => screen.getByText('buddha'));
    fireEvent.click(screen.getByText('buddha').closest('button')!);
    await waitFor(() => screen.getByTestId('lr-panel'));
    fireEvent.click(screen.getByText('Close Panel'));
    await waitFor(() =>
      expect(screen.queryByTestId('lr-panel')).toBeNull()
    );
  });
});
