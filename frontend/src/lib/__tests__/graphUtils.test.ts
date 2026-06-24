import { describe, it, expect } from 'vitest';
import { toForceGraph, getNeighbours, computeGraphStats } from '../graphUtils';
import type { GraphData } from '../../types';

const sample: GraphData = {
  nodes: [
    { note_id: 'a', title: 'A', incoming_link_count: 0, outgoing_link_count: 1 },
    { note_id: 'b', title: 'B', incoming_link_count: 1, outgoing_link_count: 0 },
    { note_id: 'c', title: 'C', incoming_link_count: 0, outgoing_link_count: 0 },
  ],
  edges: [
    { source_id: 'a', target_id: 'b' },
  ],
};

describe('toForceGraph', () => {
  it('maps nodes and links correctly', () => {
    const fg = toForceGraph(sample);
    expect(fg.nodes).toHaveLength(3);
    expect(fg.links).toHaveLength(1);
    expect(fg.links[0].source).toBe('a');
    expect(fg.links[0].target).toBe('b');
  });
});

describe('getNeighbours', () => {
  it('returns directly connected note IDs', () => {
    const neighbours = getNeighbours('a', sample);
    expect(neighbours).toContain('b');
    expect(neighbours).not.toContain('c');
  });

  it('returns empty set for orphan node', () => {
    expect(getNeighbours('c', sample)).toHaveLength(0);
  });
});

describe('computeGraphStats', () => {
  it('counts orphans correctly', () => {
    const stats = computeGraphStats(sample);
    expect(stats.orphan_count).toBe(1); // node c
    expect(stats.total_notes).toBe(3);
    expect(stats.total_links).toBe(1);
  });
});
