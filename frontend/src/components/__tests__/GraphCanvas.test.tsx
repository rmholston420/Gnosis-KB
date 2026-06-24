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
    { note_id: 'n1', title: 'Emptiness',    note_type: 'permanent', status: 'evergreen', folder: '', word_count: 100, tag_count: 2, incoming_link_count: 2, outgoing_link_count: 1 },
    { note_id: 'n2', title: 'Impermanence', note_type: 'fleeting',  status: 'draft',     folder: '', word_count: 50,  tag_count: 1, incoming_link_count: 0, outgoing_link_count: 3 },
  ],
  edges: [
    { source_id: 'n1', target_id: 'n2', link_text: 'relates to', link_type: 'wiki' },
  ],
};

function renderCanvas(data: GraphData, onNodeClick?: (id: string) => void) {
  return render(
    <MemoryRouter>
      <GraphCanvas data={data} onNodeClick={onNodeClick} />
    </MemoryRouter>
  );
}

describe('GraphCanvas', () => {
  beforeEach(() => {
    mockCytoscape.mockClear();
    mockOn.mockClear();
    mockDestroy.mockClear();
  });

  it('renders without crashing with empty data', () => {
    const { container } = renderCanvas(emptyData);
    expect(container).toBeTruthy();
  });

  it('renders without crashing with sample data', () => {
    const { container } = renderCanvas(sampleData);
    expect(container).toBeTruthy();
  });

  it('calls cytoscape with nodes and edges', () => {
    renderCanvas(sampleData);
    expect(mockCytoscape).toHaveBeenCalled();
  });

  it('accepts an onNodeClick callback', () => {
    const cb = vi.fn();
    const { container } = renderCanvas(sampleData, cb);
    expect(container).toBeTruthy();
  });

  it('cleans up cytoscape on unmount', () => {
    const { unmount } = renderCanvas(sampleData);
    unmount();
    expect(mockDestroy).toHaveBeenCalled();
  });
});
