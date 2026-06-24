/// <reference types="vitest/globals" />
import {
  toForceGraph,
  toForceGraphData,
  getNeighbours,
  computeGraphStats,
  filterToNeighborhood,
  nodeColor,
  nodeVal,
} from '../graphUtils';
import type { GraphData } from '../../types';

const sampleGraph: GraphData = {
  nodes: [
    { note_id: 'a', title: 'Alpha', type: 'permanent' },
    { note_id: 'b', title: 'Beta',  type: 'fleeting'  },
    { note_id: 'c', title: 'Gamma', type: 'project'   },
  ],
  edges: [
    { source_id: 'a', target_id: 'b', link_type: 'wikilink' },
    { source_id: 'b', target_id: 'c', link_type: 'wikilink' },
  ],
};

describe('graphUtils', () => {
  it('toForceGraph / toForceGraphData produce the same output', () => {
    const r1 = toForceGraph(sampleGraph);
    const r2 = toForceGraphData(sampleGraph);
    expect(r1).toEqual(r2);
  });

  it('maps edges to source/target strings', () => {
    const { links } = toForceGraph(sampleGraph);
    expect(links[0].source).toBe('a');
    expect(links[0].target).toBe('b');
  });

  it('getNeighbours returns direct neighbours', () => {
    const fg = toForceGraph(sampleGraph);
    const neighbours = getNeighbours(fg, 'b');
    const ids = neighbours.map((n) => n.id);
    expect(ids).toContain('a');
    expect(ids).toContain('c');
  });

  it('computeGraphStats returns correct counts', () => {
    const fg    = toForceGraph(sampleGraph);
    const stats = computeGraphStats(fg);
    expect(stats.nodeCount).toBe(3);
    expect(stats.linkCount).toBe(2);
    expect(stats.orphanCount).toBe(0);
  });

  it('filterToNeighborhood excludes distant nodes', () => {
    const fg       = toForceGraph(sampleGraph);
    const filtered = filterToNeighborhood(fg, 'a', 1);
    const ids      = filtered.nodes.map((n) => n.id);
    expect(ids).toContain('a');
    expect(ids).toContain('b');
    expect(ids).not.toContain('c');
  });

  it('nodeColor returns a hex string', () => {
    expect(nodeColor({ note_id: 'x', title: 'X', type: 'permanent' })).toMatch(/^#/);
  });

  it('nodeVal returns a positive number', () => {
    expect(nodeVal({ note_id: 'x', title: 'X' })).toBeGreaterThan(0);
  });
});
