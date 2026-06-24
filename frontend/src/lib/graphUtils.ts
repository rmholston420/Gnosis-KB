/**
 * Graph data transform utilities for react-force-graph-2d.
 * Converts raw API GraphData into the shape the renderer expects.
 *
 * Both canonical names and test-expected aliases are exported.
 */
import type { GraphData, GraphNode, GraphEdge } from '../types';

/** Node color palette keyed by note_type. */
export const NODE_COLORS: Record<string, string> = {
  permanent: '#3b82f6',
  fleeting:  '#94a3b8',
  project:   '#f59e0b',
  area:      '#10b981',
  resource:  '#8b5cf6',
  journal:   '#ec4899',
  moc:       '#ef4444',
  literature:'#f97316',
  default:   '#6b7280',
};

/** Return the display color for a node. */
export function nodeColor(node: GraphNode): string {
  return NODE_COLORS[node.type ?? 'default'] ?? NODE_COLORS['default'];
}

/** Node size — scaled by sqrt(incomingLinks + 1) so hubs are visually distinct. */
export function nodeVal(node: GraphNode): number {
  return Math.sqrt((node.incoming_link_count ?? 0) + 1) * 3;
}

/** Transform the raw API response into the {nodes, links} format react-force-graph expects. */
export function toForceGraphData(raw: GraphData): {
  nodes: Array<GraphNode & { id: string }>;
  links: Array<{ source: string; target: string; type: string }>;
} {
  return {
    nodes: raw.nodes.map((n) => ({ ...n, id: n.note_id })),
    links: raw.edges.map((e: GraphEdge) => ({
      source: e.source_id,
      target: e.target_id,
      type:   e.link_type ?? 'wikilink',
    })),
  };
}

/** Alias expected by unit tests. */
export const toForceGraph = toForceGraphData;

/**
 * Filter graph data to only include nodes within `hops` steps of `focusId`.
 * Used for neighborhood-mode rendering.
 */
export function filterToNeighborhood(
  data: ReturnType<typeof toForceGraphData>,
  focusId: string,
  hops = 1,
): ReturnType<typeof toForceGraphData> {
  const adjacent = new Set<string>([focusId]);

  for (let h = 0; h < hops; h++) {
    for (const link of data.links) {
      if (adjacent.has(link.source)) adjacent.add(link.target);
      if (adjacent.has(link.target)) adjacent.add(link.source);
    }
  }

  return {
    nodes: data.nodes.filter((n) => adjacent.has(n.id)),
    links: data.links.filter(
      (l) => adjacent.has(l.source) && adjacent.has(l.target),
    ),
  };
}

/** Alias expected by unit tests. */
export function getNeighbours(
  data: ReturnType<typeof toForceGraphData>,
  nodeId: string,
): Array<GraphNode & { id: string }> {
  const neighbourIds = new Set<string>();
  for (const link of data.links) {
    if (link.source === nodeId) neighbourIds.add(link.target);
    if (link.target === nodeId) neighbourIds.add(link.source);
  }
  return data.nodes.filter((n) => neighbourIds.has(n.id));
}

/** Compute basic graph statistics from force-graph data. Expected by unit tests. */
export function computeGraphStats(data: ReturnType<typeof toForceGraphData>): {
  nodeCount:   number;
  linkCount:   number;
  avgDegree:   number;
  orphanCount: number;
} {
  const nodeCount   = data.nodes.length;
  const linkCount   = data.links.length;
  const degree      = new Map<string, number>();
  data.nodes.forEach((n) => degree.set(n.id, 0));
  data.links.forEach((l) => {
    degree.set(l.source, (degree.get(l.source) ?? 0) + 1);
    degree.set(l.target, (degree.get(l.target) ?? 0) + 1);
  });
  const avgDegree   = nodeCount ? (linkCount * 2) / nodeCount : 0;
  const orphanCount = [...degree.values()].filter((d) => d === 0).length;
  return { nodeCount, linkCount, avgDegree, orphanCount };
}

/** Group nodes by cluster_id for community-detection coloring. */
export function clusterColor(clusterId: number): string {
  const palette = [
    '#3b82f6', '#10b981', '#f59e0b', '#ef4444',
    '#8b5cf6', '#ec4899', '#14b8a6', '#f97316',
    '#6366f1', '#84cc16',
  ];
  return palette[clusterId % palette.length];
}
