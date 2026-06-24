/**
 * GraphCanvas.test.tsx
 * ====================
 * Tests for the Cytoscape.js knowledge-graph canvas wrapper.
 *
 * Key constraint: vi.mock factories are hoisted to the top of the file by
 * Vitest's transformer BEFORE const declarations are evaluated.  Any const
 * used inside a vi.mock factory must be created via vi.hoisted() so it is
 * initialised at hoist time rather than at statement-evaluation time.
 */
import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import type { GraphData } from '../../types';

// ── Create mock objects at hoist time ────────────────────────────────────────
const { mockOn, mockDestroy, mockCytoscape } = vi.hoisted(() => {
  const mockOn      = vi.fn();
  const mockDestroy = vi.fn();
  const mockCy      = { on: mockOn, destroy: mockDestroy };
  const mockCytoscape = Object.assign(vi.fn(() => mockCy), { use: vi.fn() });
  return { mockOn, mockDestroy, mockCytoscape };
});

// ── Module mocks (hoisted; can safely reference hoisted consts) ───────────────
vi.mock('cytoscape', () => ({ default: mockCytoscape }));
vi.mock('cytoscape-fcose', () => ({ default: {} }));

const mockNavigate = vi.fn();
vi.mock('react-router-dom', async () => {
  const actual = await vi.importActual<typeof import('react-router-dom')>('react-router-dom');
  return { ...actual, useNavigate: () => mockNavigate };
});

// Import component AFTER mocks are registered
import GraphCanvas from '../GraphCanvas';

const emptyData: GraphData = { nodes: [], edges: [] };

const sampleData: GraphData = {
  nodes: [
    { id: 'n1', title: 'Emptiness',    slug: 'emptiness',    note_type: 'permanent', incoming_link_count: 2, outgoing_link_count: 1 },
    { id: 'n2', title: 'Impermanence', slug: 'impermanence', note_type: 'fleeting',  incoming_link_count: 0, outgoing_link_count: 3 },
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
    const div = document.querySelector('.bg-bg-primary') as HTMLElement;
    expect(div).toBeInTheDocument();
  });

  it('renders container with minHeight style', () => {
    renderCanvas(emptyData);
    const div = document.querySelector('[style]') as HTMLElement;
    expect(div?.style.minHeight).toBe('400px');
  });

  it('calls cytoscape() on mount', () => {
    renderCanvas(emptyData);
    expect(mockCytoscape).toHaveBeenCalledTimes(1);
  });

  it('passes empty elements array for empty data', () => {
    renderCanvas(emptyData);
    const opts = mockCytoscape.mock.calls[0][0] as { elements: unknown[] };
    expect(opts.elements).toHaveLength(0);
  });

  it('maps nodes into cytoscape elements with correct id', () => {
    renderCanvas(sampleData);
    const opts = mockCytoscape.mock.calls[0][0] as { elements: Array<{ data: { id: string } }> };
    const ids = opts.elements.map((e) => e.data.id);
    expect(ids).toContain('n1');
    expect(ids).toContain('n2');
  });

  it('maps edges with composite id "source-target"', () => {
    renderCanvas(sampleData);
    const opts = mockCytoscape.mock.calls[0][0] as { elements: Array<{ data: { id: string; source?: string } }> };
    const edge = opts.elements.find((e) => e.data.source === 'n1');
    expect(edge?.data.id).toBe('n1-n2');
  });

  it('registers a tap listener on nodes', () => {
    renderCanvas(sampleData);
    expect(mockOn).toHaveBeenCalledWith('tap', 'node', expect.any(Function));
  });

  it('calls onNodeClick with node id when tap fires and callback is provided', () => {
    const onNodeClick = vi.fn();
    renderCanvas(sampleData, onNodeClick);
    const tapCall = mockOn.mock.calls.find(([event]) => event === 'tap')!;
    const tapHandler = tapCall[2] as (e: { target: { id: () => string } }) => void;
    tapHandler({ target: { id: () => 'n1' } });
    expect(onNodeClick).toHaveBeenCalledWith('n1');
    expect(mockNavigate).not.toHaveBeenCalled();
  });

  it('navigates to /notes/:id when no onNodeClick provided', () => {
    renderCanvas(sampleData);
    const tapCall = mockOn.mock.calls.find(([event]) => event === 'tap')!;
    const tapHandler = tapCall[2] as (e: { target: { id: () => string } }) => void;
    tapHandler({ target: { id: () => 'n2' } });
    expect(mockNavigate).toHaveBeenCalledWith('/notes/n2');
  });

  it('destroys previous cytoscape instance when data prop changes', () => {
    const { rerender } = renderCanvas(sampleData);
    rerender(
      <MemoryRouter>
        <GraphCanvas data={emptyData} />
      </MemoryRouter>
    );
    // destroy is called by the useEffect cleanup on unmount/dep change
    expect(mockDestroy).toHaveBeenCalled();
  });
});
