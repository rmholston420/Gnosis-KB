/**
 * GraphCanvas.test.tsx
 * ====================
 * Tests for the Cytoscape.js knowledge-graph canvas wrapper.
 *
 * Cytoscape requires a DOM container with real dimensions, which jsdom
 * doesn't provide.  We mock the entire `cytoscape` module so tests can
 * verify that:
 *  - The component mounts without error for empty / populated data
 *  - cytoscape() is called with the right elements structure
 *  - Node tap triggers onNodeClick callback (or navigate fallback)
 *  - The component re-initialises (destroy + re-create) when data changes
 *  - The container div is rendered with the correct class
 */
import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import type { GraphData } from '../../types';

// ── Cytoscape mock ───────────────────────────────────────────────────────────
const mockOn       = vi.fn();
const mockDestroy  = vi.fn();
const mockCy       = { on: mockOn, destroy: mockDestroy };
const mockCytoscape = vi.fn(() => mockCy);
mockCytoscape.use = vi.fn();

vi.mock('cytoscape', () => ({ default: mockCytoscape }));
vi.mock('cytoscape-fcose', () => ({ default: {} }));

const mockNavigate = vi.fn();
vi.mock('react-router-dom', async () => {
  const actual = await vi.importActual<typeof import('react-router-dom')>('react-router-dom');
  return { ...actual, useNavigate: () => mockNavigate };
});

import GraphCanvas from '../GraphCanvas';

const emptyData: GraphData = { nodes: [], edges: [] };

const sampleData: GraphData = {
  nodes: [
    { id: 'n1', title: 'Emptiness',   slug: 'emptiness',   note_type: 'permanent',  incoming_link_count: 2, outgoing_link_count: 1 },
    { id: 'n2', title: 'Impermanence', slug: 'impermanence', note_type: 'fleeting',   incoming_link_count: 0, outgoing_link_count: 3 },
  ],
  edges: [
    { source: 'n1', target: 'n2', link_text: 'relates to' },
  ],
};

function renderCanvas(data: GraphData, onNodeClick?: (id: string) => void) {
  return render(
    <MemoryRouter>
      <GraphCanvas data={data} onNodeClick={onNodeClick} />
    </MemoryRouter>
  );
}

beforeEach(() => {
  mockCytoscape.mockClear();
  mockOn.mockClear();
  mockDestroy.mockClear();
  mockNavigate.mockReset();
});

describe('GraphCanvas', () => {
  it('renders the container div', () => {
    renderCanvas(emptyData);
    // Container must be present (Cytoscape attaches to it)
    const div = document.querySelector('.bg-bg-primary') as HTMLElement;
    expect(div).toBeInTheDocument();
  });

  it('calls cytoscape() on mount with empty data', () => {
    renderCanvas(emptyData);
    expect(mockCytoscape).toHaveBeenCalledTimes(1);
    const opts = mockCytoscape.mock.calls[0][0] as { elements: unknown[] };
    expect(opts.elements).toHaveLength(0);
  });

  it('maps nodes to cytoscape elements', () => {
    renderCanvas(sampleData);
    const opts = mockCytoscape.mock.calls[0][0] as { elements: Array<{ data: { id: string } }> };
    const nodeIds = opts.elements.map((e) => e.data.id);
    expect(nodeIds).toContain('n1');
    expect(nodeIds).toContain('n2');
  });

  it('maps edges to cytoscape elements with composite id', () => {
    renderCanvas(sampleData);
    const opts = mockCytoscape.mock.calls[0][0] as { elements: Array<{ data: { id: string; source?: string } }> };
    const edge = opts.elements.find((e) => e.data.source === 'n1');
    expect(edge).toBeDefined();
    expect(edge?.data.id).toBe('n1-n2');
  });

  it('registers a tap listener on nodes', () => {
    renderCanvas(sampleData);
    expect(mockOn).toHaveBeenCalledWith('tap', 'node', expect.any(Function));
  });

  it('calls onNodeClick with node id when tap fires and callback provided', () => {
    const onNodeClick = vi.fn();
    renderCanvas(sampleData, onNodeClick);
    const [[, , tapHandler]] = mockOn.mock.calls as [[string, string, (e: { target: { id: () => string } }) => void]];
    tapHandler({ target: { id: () => 'n1' } });
    expect(onNodeClick).toHaveBeenCalledWith('n1');
    expect(mockNavigate).not.toHaveBeenCalled();
  });

  it('navigates to /notes/:id when no onNodeClick provided', () => {
    renderCanvas(sampleData);
    const [[, , tapHandler]] = mockOn.mock.calls as [[string, string, (e: { target: { id: () => string } }) => void]];
    tapHandler({ target: { id: () => 'n2' } });
    expect(mockNavigate).toHaveBeenCalledWith('/notes/n2');
  });

  it('destroys previous instance when data changes', () => {
    const { rerender } = renderCanvas(sampleData);
    rerender(
      <MemoryRouter>
        <GraphCanvas data={{ nodes: [], edges: [] }} />
      </MemoryRouter>
    );
    // destroy should be called once for the first instance before re-creating
    expect(mockDestroy).toHaveBeenCalled();
  });

  it('renders with minHeight style', () => {
    renderCanvas(emptyData);
    const container = document.querySelector('[style*="minHeight"]') as HTMLElement;
    expect(container).toBeInTheDocument();
  });
});
