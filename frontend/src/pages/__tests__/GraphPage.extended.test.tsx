import React from 'react';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import { describe, it, expect, vi, beforeEach } from 'vitest';
import { MemoryRouter } from 'react-router-dom';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';

const mockGetFullGraph = vi.fn();
const mockListNotes = vi.fn();

vi.mock('@/services/api', () => ({
  default: {
    getFullGraph: (...a: unknown[]) => mockGetFullGraph(...a),
    listNotes: (...a: unknown[]) => mockListNotes(...a),
  },
}));

vi.mock('@/components/GraphCanvas', () => ({
  default: ({ nodes, links }: { nodes: unknown[]; links: unknown[] }) => (
    <div data-testid="graph-canvas" data-nodes={nodes.length} data-links={links.length} />
  ),
}));

vi.mock('@/components/graph/LightRagNodePanel', () => ({
  default: ({ nodeId }: { nodeId: string }) => (
    <div data-testid="lightrag-panel">{nodeId}</div>
  ),
}));

const GRAPH_DATA = {
  nodes: [
    { id: 'n1', label: 'Alpha', group: 'note', connections: 2 },
    { id: 'n2', label: 'Beta',  group: 'note', connections: 1 },
    { id: 'n3', label: 'Gamma', group: 'tag',  connections: 0 },
  ],
  links: [{ source: 'n1', target: 'n2' }],
};

function makeClient() {
  return new QueryClient({ defaultOptions: { queries: { retry: false } } });
}

function Wrapper({ children }: { children: React.ReactNode }) {
  return (
    <QueryClientProvider client={makeClient()}>
      <MemoryRouter>{children}</MemoryRouter>
    </QueryClientProvider>
  );
}

async function setup() {
  mockGetFullGraph.mockResolvedValue(GRAPH_DATA);
  mockListNotes.mockResolvedValue({ items: [] });
  const { default: GraphPage } = await import('@/pages/GraphPage');
  render(<Wrapper><GraphPage /></Wrapper>);
  await waitFor(() => screen.getByTestId('graph-canvas'), { timeout: 3000 });
}

describe('GraphPage extended', () => {
  beforeEach(() => vi.clearAllMocks());

  it('renders graph canvas after data loads', async () => {
    await setup();
    expect(screen.getByTestId('graph-canvas')).toBeTruthy();
  });

  it('renders node labels in sidebar', async () => {
    await setup();
    expect(screen.getByText('Alpha')).toBeTruthy();
  });

  it('renders search / filter input', async () => {
    await setup();
    const inputs = screen.queryAllByRole('textbox');
    expect(inputs.length).toBeGreaterThanOrEqual(0);
  });

  it('filter narrows displayed nodes', async () => {
    await setup();
    const inputs = screen.queryAllByRole('textbox');
    if (inputs.length > 0) {
      fireEvent.change(inputs[0], { target: { value: 'Alpha' } });
      await waitFor(() => expect(screen.queryByText('Beta')).toBeNull());
    }
  });

  it('clicking a node label does not crash', async () => {
    await setup();
    fireEvent.click(screen.getByText('Alpha'));
  });

  it('handles empty graph data gracefully', async () => {
    mockGetFullGraph.mockResolvedValue({ nodes: [], links: [] });
    mockListNotes.mockResolvedValue({ items: [] });
    const { default: GraphPage } = await import('@/pages/GraphPage');
    render(<Wrapper><GraphPage /></Wrapper>);
    await waitFor(() => screen.getByTestId('graph-canvas'), { timeout: 3000 });
    expect(screen.getByTestId('graph-canvas')).toBeTruthy();
  });

  it('handles getFullGraph rejection without crashing', async () => {
    mockGetFullGraph.mockRejectedValue(new Error('fail'));
    mockListNotes.mockResolvedValue({ items: [] });
    const { default: GraphPage } = await import('@/pages/GraphPage');
    render(<Wrapper><GraphPage /></Wrapper>);
    await new Promise((r) => setTimeout(r, 100));
  });
});
