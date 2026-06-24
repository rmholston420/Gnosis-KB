/**
 * Graph data transform utilities for react-force-graph-2d.
 */
import type { GraphData, GraphNode, GraphEdge } from '../types';

export const NODE_COLORS: Record<string, string> = {
  permanent: '#3b82f6',
  fleeting: '#94a3b8',
  project: '#f59e0b',
  area: '#10b981',
  resource: '#8b5cf6',
  journal: '#ec4899',
  moc: '#ef4444',
  literature: '#f97316',
  default: '#6b7280',
};

export function nodeColor(node: GraphNode): string {
  return NODE_COLORS[node.type ?? 'default'] ?? NODE_COLORS.default;
}

export function nodeVal(node: GraphNode): number {
  return Math.sqrt((node.incoming_link_count ?? 0) + 1) * 3;
}

export function toForceGraphData(raw: GraphData): {
  nodes: Array<GraphNode & { id: string }>;
  links: Array<{ source: string; target: string; type: string }>;
} {
  return {
    nodes: raw.nodes.map((n) => ({ ...n, id: n.note_id })),
    links: raw.edges.map((e: GraphEdge) => ({
      source: e.source_id,
      target: e.target_id,
      type: e.link_type ?? 'wikilink',
    })),
  };
}

export const toForceGraph = toForceGraphData;

export function filterToNeighborhood(
  data: ReturnType<typeof toForceGraphData>,
  focusId: string,
  hops = 1,
): ReturnType<typeof toForceGraphData> {
  let frontier = new Set<string>([focusId]);
  const visited = new Set<string>([focusId]);

  for (let h = 0; h < hops; h += 1) {
    const nextFrontier = new Set<string>();
    for (const link of data.links) {
      if (frontier.has(link.source) && !visited.has(link.target)) {
        nextFrontier.add(link.target);
      }
      if (frontier.has(link.target) && !visited.has(link.source)) {
        nextFrontier.add(link.source);
      }
    }
    nextFrontier.forEach((id) => visited.add(id));
    frontier = nextFrontier;
    if (frontier.size === 0) break;
  }

  return {
    nodes: data.nodes.filter((n) => visited.has(n.id)),
    links: data.links.filter((l) => visited.has(l.source) && visited.has(l.target)),
  };
}

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

export function computeGraphStats(data: ReturnType<typeof toForceGraphData>): {
  nodeCount: number;
  linkCount: number;
  avgDegree: number;
  orphanCount: number;
} {
  const nodeCount = data.nodes.length;
  const linkCount = data.links.length;
  const degree = new Map<string, number>();
  data.nodes.forEach((n) => degree.set(n.id, 0));
  data.links.forEach((l) => {
    degree.set(l.source, (degree.get(l.source) ?? 0) + 1);
    degree.set(l.target, (degree.get(l.target) ?? 0) + 1);
  });
  const avgDegree = nodeCount ? (linkCount * 2) / nodeCount : 0;
  const orphanCount = [...degree.values()].filter((d) => d === 0).length;
  return { nodeCount, linkCount, avgDegree, orphanCount };
}

export function clusterColor(clusterId: number): string {
  const palette = [
    '#3b82f6', '#10b981', '#f59e0b', '#ef4444',
    '#8b5cf6', '#ec4899', '#14b8a6', '#f97316',
    '#6366f1', '#84cc16',
  ];
  return palette[clusterId % palette.length];
}
