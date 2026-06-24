import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import type { GraphData } from '../../types';

const { mockOn, mockDestroy, mockCytoscape } = vi.hoisted(() => {
  const mockOn = vi.fn();
  const mockDestroy = vi.fn();
  const mockCy = { on: mockOn, destroy: mockDestroy };
  const mockCytoscape = Object.assign(vi.fn(() => mockCy), { use: vi.fn() });
  return { mockOn, mockDestroy, mockCytoscape };
});

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
    { id: 'n1', title: 'Emptiness', note_type: 'permanent', status: 'evergreen', folder: '', word_count: 100, tag_count: 2, incoming_link_count: 2, outgoing_link_count: 1 },
    { id: 'n2', title: 'Impermanence', note_type: 'fleeting', status: 'draft', folder: '', word_count: 50, tag_count: 1, incoming_link_count: 0, outgoing_link_count: 3 },
  ],
  edges: [
    { source: 'n1', target: 'n2', link_text: 'relates to', link_type: 'wiki' },
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
  it('calls cytoscape on mount', () => {
    renderCanvas(emptyData);
    expect(mockCytoscape).toHaveBeenCalledTimes(1);
  });

  it('passes empty elements for empty data', () => {
    renderCanvas(emptyData);
    const firstCall = (mockCytoscape.mock.calls as unknown[][])[0];
    expect(firstCall).toBeTruthy();
    const opts = (firstCall?.[0] ?? {}) as { elements: unknown[] };
    expect(opts.elements).toHaveLength(0);
  });

  it('maps edge id as source-target', () => {
    renderCanvas(sampleData);
    const firstCall = (mockCytoscape.mock.calls as unknown[][])[0];
    const opts = (firstCall?.[0] ?? {}) as { elements: Array<{ data: { id: string; source?: string } }> };
    const edge = opts.elements.find((e) => e.data.source === 'n1');
    expect(edge?.data.id).toBe('n1-n2');
  });
});
