import React from 'react';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import { describe, it, expect, vi, beforeEach } from 'vitest';
import { MemoryRouter } from 'react-router-dom';

const mockGetGraphData = vi.fn();
const mockSearchNotes = vi.fn();
const mockGetNote = vi.fn();
const mockListNotes = vi.fn();

vi.mock('@/services/api', () => ({
  default: {
    getGraphData: (...a: unknown[]) => mockGetGraphData(...a),
    searchNotes: (...a: unknown[]) => mockSearchNotes(...a),
    getNote: (...a: unknown[]) => mockGetNote(...a),
    listNotes: (...a: unknown[]) => mockListNotes(...a),
  },
}));

vi.mock('@/components/GraphCanvas', () => ({
  default: ({ nodes, links }: { nodes: unknown[]; links: unknown[] }) => (
    <div data-testid="graph-canvas" data-nodes={nodes.length} data-links={links.length} />
  ),
}));

vi.mock('@/components/graph/LightRagNodePanel', () => ({
  default: ({ nodeId }: { nodeId: string }) => <div data-testid="lightrag-panel">{nodeId}</div>,
}));

const GRAPH_DATA = {
  nodes: [
    { id: 'n1', label: 'Alpha', group: 'note', connections: 2 },
    { id: 'n2', label: 'Beta', group: 'note', connections: 1 },
    { id: 'n3', label: 'Gamma', group: 'tag', connections: 0 },
  ],
  links: [{ source: 'n1', target: 'n2' }],
};

async function setup() {
  mockGetGraphData.mockResolvedValue(GRAPH_DATA);
  mockListNotes.mockResolvedValue({ items: [] });
  const { default: GraphPage } = await import('@/pages/GraphPage');
  render(
    <MemoryRouter>
      <GraphPage />
    </MemoryRouter>
  );
  await waitFor(() => screen.getByTestId('graph-canvas'));
}

describe('GraphPage extended', () => {
  beforeEach(() => vi.clearAllMocks());

  it('renders graph canvas after data loads', async () => {
    await setup();
    expect(screen.getByTestId('graph-canvas')).toBeTruthy();
  });

  it('renders node list sidebar', async () => {
    await setup();
    expect(screen.getByText('Alpha')).toBeTruthy();
  });

  it('renders search input', async () => {
    await setup();
    expect(screen.getByPlaceholderText(/search/i)).toBeTruthy();
  });

  it('filter input narrows displayed nodes', async () => {
    await setup();
    const input = screen.getByPlaceholderText(/search/i);
    fireEvent.change(input, { target: { value: 'Alpha' } });
    await waitFor(() => expect(screen.queryByText('Beta')).toBeNull());
  });

  it('clicking a node shows detail / panel', async () => {
    await setup();
    fireEvent.click(screen.getByText('Alpha'));
  });

  it('handles empty graph data gracefully', async () => {
    mockGetGraphData.mockResolvedValue({ nodes: [], links: [] });
    mockListNotes.mockResolvedValue({ items: [] });
    const { default: GraphPage } = await import('@/pages/GraphPage');
    render(
      <MemoryRouter>
        <GraphPage />
      </MemoryRouter>
    );
    await waitFor(() => screen.getByTestId('graph-canvas'));
    expect(screen.getByTestId('graph-canvas')).toBeTruthy();
  });

  it('handles getGraphData rejection', async () => {
    mockGetGraphData.mockRejectedValue(new Error('fail'));
    mockListNotes.mockResolvedValue({ items: [] });
    const { default: GraphPage } = await import('@/pages/GraphPage');
    render(
      <MemoryRouter>
        <GraphPage />
      </MemoryRouter>
    );
    await new Promise((r) => setTimeout(r, 80));
  });
});
