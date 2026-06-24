/**
 * GraphPage.test.tsx
 * Tests the full GraphPage component: tab switching, toolbar, stats, and
 * LightRAG entity list.
 */
import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { MemoryRouter } from 'react-router-dom';
import GraphPage from '../GraphPage';
import * as apiModule from '../../services/api';

// ── Mock react-force-graph-2d so tests don't spin up WebGL ─────────────
vi.mock('react-force-graph-2d', () => ({
  default: vi.fn(() => <canvas data-testid="force-graph" />),
}));

// ── Silence ResizeObserver (jsdom doesn't have it) ─────────────────────
global.ResizeObserver = class ResizeObserver {
  observe()   {}
  unobserve() {}
  disconnect() {}
};

// ── Minimal graph fixture ──────────────────────────────────────────────
const GRAPH_DATA = {
  nodes: [
    { note_id: 'n1', id: 'n1', title: 'Alpha', type: 'permanent', incoming_link_count: 2 },
    { note_id: 'n2', id: 'n2', title: 'Beta',  type: 'fleeting',  incoming_link_count: 0 },
  ],
  edges: [
    { source_id: 'n1', target_id: 'n2', type: 'wikilink' },
  ],
};

const ENTITY_DATA = {
  entities: [
    { id: 'e1', label: 'Tibetan Buddhism', type: 'concept', description: 'Vajrayana tradition' },
    { id: 'e2', label: 'Dzogchen',         type: 'practice' },
  ],
};

const LIGHTRAG_HEALTH = { node_count: 42, edge_count: 108, is_empty: false };

function makeClient() {
  return new QueryClient({
    defaultOptions: { queries: { retry: false } },
  });
}

function Wrapper({ children }: { children: React.ReactNode }) {
  return (
    <QueryClientProvider client={makeClient()}>
      <MemoryRouter>{children}</MemoryRouter>
    </QueryClientProvider>
  );
}

beforeEach(() => {
  vi.spyOn(apiModule.default, 'getFullGraph').mockResolvedValue(GRAPH_DATA as never);
  vi.spyOn(apiModule.default, 'getGraphEntities').mockResolvedValue(ENTITY_DATA as never);
  vi.spyOn(apiModule.default, 'getLightRagGraph').mockResolvedValue(LIGHTRAG_HEALTH as never);
  vi.spyOn(apiModule.default, 'triggerVaultSync').mockResolvedValue({ status: 'ok' } as never);
});

describe('GraphPage', () => {
  it('renders the Knowledge Graph heading', async () => {
    render(<GraphPage />, { wrapper: Wrapper });
    expect(screen.getByText('Knowledge Graph')).toBeInTheDocument();
  });

  it('shows Wikilinks and LightRAG Knowledge tabs', () => {
    render(<GraphPage />, { wrapper: Wrapper });
    expect(screen.getByRole('button', { name: /wikilinks/i })).toBeInTheDocument();
    expect(screen.getByRole('button', { name: /lightrag knowledge/i })).toBeInTheDocument();
  });

  it('renders the node filter toolbar input', () => {
    render(<GraphPage />, { wrapper: Wrapper });
    expect(screen.getByPlaceholderText(/filter nodes/i)).toBeInTheDocument();
  });

  it('renders Refresh button', () => {
    render(<GraphPage />, { wrapper: Wrapper });
    expect(screen.getByRole('button', { name: /refresh/i })).toBeInTheDocument();
  });

  it('shows node + edge stat badges after graph loads', async () => {
    render(<GraphPage />, { wrapper: Wrapper });
    await waitFor(() => {
      expect(screen.getByText(/nodes/i)).toBeInTheDocument();
      expect(screen.getByText(/edges/i)).toBeInTheDocument();
    });
  });

  it('switches to LightRAG tab and shows entity filter input', async () => {
    render(<GraphPage />, { wrapper: Wrapper });
    fireEvent.click(screen.getByRole('button', { name: /lightrag knowledge/i }));
    await waitFor(() => {
      expect(screen.getByPlaceholderText(/filter entities/i)).toBeInTheDocument();
    });
  });

  it('renders LightRAG entity list after tab switch', async () => {
    render(<GraphPage />, { wrapper: Wrapper });
    fireEvent.click(screen.getByRole('button', { name: /lightrag knowledge/i }));
    await waitFor(() => {
      expect(screen.getByText('Tibetan Buddhism')).toBeInTheDocument();
      expect(screen.getByText('Dzogchen')).toBeInTheDocument();
    });
  });

  it('filters entity list by search term', async () => {
    render(<GraphPage />, { wrapper: Wrapper });
    fireEvent.click(screen.getByRole('button', { name: /lightrag knowledge/i }));
    await waitFor(() => screen.getByText('Tibetan Buddhism'));
    fireEvent.change(screen.getByPlaceholderText(/filter entities/i), {
      target: { value: 'dzog' },
    });
    expect(screen.getByText('Dzogchen')).toBeInTheDocument();
    expect(screen.queryByText('Tibetan Buddhism')).not.toBeInTheDocument();
  });

  it('filtering node list by query hides non-matching nodes from the canvas', async () => {
    render(<GraphPage />, { wrapper: Wrapper });
    await waitFor(() => screen.getByText(/nodes/i));
    fireEvent.change(screen.getByPlaceholderText(/filter nodes/i), {
      target: { value: 'Alpha' },
    });
    // After filtering, only 1 node should be shown in the stats badge
    await waitFor(() => {
      expect(screen.getByText(/1 nodes/i)).toBeInTheDocument();
    });
  });
});
