/**
 * GraphPage.extended.test.tsx
 * Targets lines: 315-317, 427-471, 518-524, 586-592
 * - LightRAG tab: entity sidebar, filter, entity click → LightRagNodePanel
 * - Wikilinks tab: node click → detail panel, hover, close panel
 */
import React from 'react';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { MemoryRouter } from 'react-router-dom';

vi.mock('react-force-graph-2d', () => ({
  default: vi.fn(({ graphData, onNodeClick, onNodeHover }: {
    graphData: { nodes: unknown[] };
    onNodeClick?: (n: unknown) => void;
    onNodeHover?: (n: unknown) => void;
  }) =>
    React.createElement('div', { 'data-testid': 'force-graph' },
      React.createElement('button', {
        'data-testid': 'click-node',
        onClick: () => onNodeClick?.({
          id: 'n1', title: 'EEG Note', note_type: 'permanent',
          status: 'draft', folder: '10',
        }),
      }, 'click-node'),
      React.createElement('button', {
        'data-testid': 'hover-node',
        onClick: () => onNodeHover?.({
          id: 'n2', title: 'BCI Project', note_type: 'project',
          status: 'evergreen', folder: '20',
        }),
      }, 'hover-node'),
    )
  ),
}));

Object.defineProperty(HTMLCanvasElement.prototype, 'getContext', {
  value: () => null, configurable: true,
});

vi.mock('@/components/graph/LightRagNodePanel', () => ({
  LightRagNodePanel: ({ entity, onClose }: {
    entity: { id: string; label: string };
    onClose: () => void;
  }) => (
    <div data-testid="lr-node-panel">
      <span>{entity.id}</span>
      <button onClick={onClose}>close-panel</button>
    </div>
  ),
}));

const GRAPH_DATA = {
  nodes: [
    { id: 'n1', title: 'EEG Note', note_type: 'permanent', status: 'draft',
      folder: '10', incoming_link_count: 1, outgoing_link_count: 2 },
    { id: 'n2', title: 'BCI Project', note_type: 'project', status: 'evergreen',
      folder: '20', incoming_link_count: 0, outgoing_link_count: 0 },
  ],
  edges: [{ source: 'n1', target: 'n2', link_text: '' }],
};

const LR_GRAPH_DATA = { entities: [], relations: [] };

const ENTITIES = [
  { id: 'EEG', label: 'EEG Signals', cluster: 0 },
  { id: 'LightRAG', label: 'LightRAG AI', cluster: 1 },
  { id: 'BCI', label: 'Brain-Computer Interface', cluster: 2 },
];

const LR_NODE_DETAIL = {
  id: 'EEG', description: 'EEG signal processing', labels: [], relations: [],
};

function makeResponse(body: unknown, ok = true): Response {
  return {
    ok, status: ok ? 200 : 500,
    json: () => Promise.resolve(body),
    text: () => Promise.resolve(JSON.stringify(body)),
    clone() { return this; },
  } as unknown as Response;
}

function makeDefaultFetch(overrides: Record<string, unknown> = {}) {
  return vi.fn((input: RequestInfo | URL) => {
    const url = typeof input === 'string' ? input : (input as Request).url;
    for (const [pat, data] of Object.entries(overrides)) {
      if (url.includes(pat)) return Promise.resolve(makeResponse(data));
    }
    if (url.includes('/graph/entities')) return Promise.resolve(makeResponse({ entities: ENTITIES }));
    if (url.includes('/graph/lightrag'))  return Promise.resolve(makeResponse(LR_GRAPH_DATA));
    if (url.includes('/graph'))           return Promise.resolve(makeResponse(GRAPH_DATA));
    return Promise.resolve(makeResponse({}));
  });
}

import GraphPage from '../GraphPage';

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
  vi.stubGlobal('fetch', makeDefaultFetch());
  vi.spyOn(Storage.prototype, 'getItem').mockReturnValue(null);
});
afterEach(() => { vi.unstubAllGlobals(); vi.restoreAllMocks(); });

describe('GraphPage — LightRAG tab entity sidebar', () => {
  it('switches to LightRAG tab and shows Entities heading', async () => {
    wrap();
    fireEvent.click(screen.getByRole('button', { name: /lightrag knowledge/i }));
    await waitFor(() =>
      expect(screen.getByText('Entities')).toBeInTheDocument()
    );
  });

  it('shows entity count badge', async () => {
    wrap();
    fireEvent.click(screen.getByRole('button', { name: /lightrag knowledge/i }));
    await waitFor(() =>
      expect(screen.getByText(String(ENTITIES.length))).toBeInTheDocument()
    );
  });

  it('filters entity list via search input (lines 315-317)', async () => {
    wrap();
    fireEvent.click(screen.getByRole('button', { name: /lightrag knowledge/i }));
    await waitFor(() => screen.getByText('EEG'));
    fireEvent.change(screen.getByPlaceholderText(/filter entities/i), { target: { value: 'BCI' } });
    await waitFor(() => expect(screen.getByText('BCI')).toBeInTheDocument());
    expect(screen.queryByText('LightRAG')).toBeNull();
  });

  it('shows "No entities found" when filter yields nothing', async () => {
    wrap();
    fireEvent.click(screen.getByRole('button', { name: /lightrag knowledge/i }));
    await waitFor(() => screen.getByText('EEG'));
    fireEvent.change(screen.getByPlaceholderText(/filter entities/i), { target: { value: 'XYZZZZ' } });
    await waitFor(() => expect(screen.getByText(/no entities found/i)).toBeInTheDocument());
  });

  it('clicking an entity shows the LightRagNodePanel (lines 518-524)', async () => {
    vi.stubGlobal('fetch', makeDefaultFetch({ '/graph/entity/EEG': LR_NODE_DETAIL }));
    wrap();
    fireEvent.click(screen.getByRole('button', { name: /lightrag knowledge/i }));
    await waitFor(() => screen.getByText('EEG'));
    fireEvent.click(screen.getByText('EEG'));
    await waitFor(() =>
      expect(screen.getByTestId('lr-node-panel')).toBeInTheDocument()
    );
  });

  it('closes LightRagNodePanel on close (lines 586-592)', async () => {
    vi.stubGlobal('fetch', makeDefaultFetch({ '/graph/entity/EEG': LR_NODE_DETAIL }));
    wrap();
    fireEvent.click(screen.getByRole('button', { name: /lightrag knowledge/i }));
    await waitFor(() => screen.getByText('EEG'));
    fireEvent.click(screen.getByText('EEG'));
    await waitFor(() => screen.getByTestId('lr-node-panel'));
    fireEvent.click(screen.getByText('close-panel'));
    await waitFor(() => expect(screen.queryByTestId('lr-node-panel')).toBeNull());
  });
});

describe('GraphPage — wikilinks node detail panel (lines 427-471)', () => {
  it('shows node detail panel on node click', async () => {
    wrap();
    await waitFor(() => screen.getByTestId('force-graph'));
    fireEvent.click(screen.getByTestId('click-node'));
    await waitFor(() => expect(screen.getByText('EEG Note')).toBeInTheDocument());
  });

  it('shows Open Note button in node detail panel', async () => {
    wrap();
    await waitFor(() => screen.getByTestId('force-graph'));
    fireEvent.click(screen.getByTestId('click-node'));
    await waitFor(() => expect(screen.getByRole('button', { name: /open note/i })).toBeInTheDocument());
  });

  it('closes node panel via X button', async () => {
    wrap();
    await waitFor(() => screen.getByTestId('force-graph'));
    fireEvent.click(screen.getByTestId('click-node'));
    await waitFor(() => screen.getByText('EEG Note'));
    // The close button uses &#x2715; (✕)
    const xBtn = screen.getByText('\u2715');
    fireEvent.click(xBtn);
    await waitFor(() => expect(screen.queryByText('EEG Note')).toBeNull());
  });

  it('shows hovered node info in detail panel', async () => {
    wrap();
    await waitFor(() => screen.getByTestId('force-graph'));
    fireEvent.click(screen.getByTestId('hover-node'));
    await waitFor(() => expect(screen.getByText('BCI Project')).toBeInTheDocument());
  });
});
