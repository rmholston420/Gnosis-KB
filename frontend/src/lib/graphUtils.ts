/**
 * Graph data transform utilities for react-force-graph-2d.
 * Converts raw API GraphData into the shape the renderer expects.
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

/** Returns the fill color for a graph node based on its note_type. */
export function nodeColor(node: GraphNode): string {
  return NODE_COLORS[node.type ?? 'default'] ?? NODE_COLORS['default'];
}

/**
 * Returns the visual size (area) of a node.
 * Scaled by incoming link count so hub nodes appear larger.
 */
export function nodeVal(node: GraphNode): number {
  const links = (node as GraphNode & { incoming_link_count?: number }).incoming_link_count ?? 0;
  return Math.max(4, 4 + links * 2);
}

/** Map cluster index → color from the NODE_COLORS palette. */
export function clusterColor(idx?: number): string {
  const palette = Object.values(NODE_COLORS);
  return palette[(idx ?? 0) % palette.length];
}

export interface ForceGraphNode {
  id:                  string;
  title:               string;
  type:                string;
  incoming_link_count: number;
  cluster_id?:         number;
  x?: number;
  y?: number;
}

export interface ForceGraphLink {
  source: string;
  target: string;
  type:   string;
}

export interface ForceGraphData {
  nodes: ForceGraphNode[];
  links: ForceGraphLink[];
}

/**
 * toForceGraphData converts the raw API GraphData (nodes + edges) into the
 * { nodes, links } shape expected by react-force-graph-2d.
 *
 * Edge endpoints are stored as plain string IDs so the library can resolve
 * them to node objects internally — do NOT pass node objects here.
 */
export function toForceGraphData(graph: GraphData): ForceGraphData {
  const nodes: ForceGraphNode[] = (graph.nodes ?? []).map((n: GraphNode) => ({
    id:                  n.note_id ?? n.id ?? '',
    title:               n.title ?? '',
    type:                n.type ?? n.note_type ?? 'default',
    incoming_link_count: (n as GraphNode & { incoming_link_count?: number }).incoming_link_count ?? 0,
    cluster_id:          (n as GraphNode & { cluster_id?: number }).cluster_id,
  }));

  const links: ForceGraphLink[] = (graph.edges ?? []).map((e: GraphEdge) => ({
    source: e.source_id ?? e.source ?? '',
    target: e.target_id ?? e.target ?? '',
    type:   e.type ?? e.link_type ?? 'wikilink',
  }));

  return { nodes, links };
}

/**
 * toForceGraph is an alias for toForceGraphData.
 * Tests assert both produce identical output.
 */
export const toForceGraph = toForceGraphData;

/**
 * getNeighbours returns all nodes directly connected to a given node id
 * (both incoming and outgoing edges).
 */
export function getNeighbours(graph: ForceGraphData, nodeId: string): ForceGraphNode[] {
  const neighbourIds = new Set<string>();
  for (const link of graph.links) {
    const src = typeof link.source === 'string' ? link.source : (link.source as unknown as ForceGraphNode).id;
    const tgt = typeof link.target === 'string' ? link.target : (link.target as unknown as ForceGraphNode).id;
    if (src === nodeId) neighbourIds.add(tgt);
    if (tgt === nodeId) neighbourIds.add(src);
  }
  return graph.nodes.filter((n) => neighbourIds.has(n.id));
}

/** Stats summary for a force-graph dataset. */
export interface GraphComputedStats {
  nodeCount:   number;
  linkCount:   number;
  orphanCount: number;
  density:     number;
}

/**
 * computeGraphStats derives simple statistics from a ForceGraphData.
 */
export function computeGraphStats(graph: ForceGraphData): GraphComputedStats {
  const { nodes, links } = graph;
  const connectedIds = new Set<string>();
  for (const link of links) {
    const src = typeof link.source === 'string' ? link.source : (link.source as unknown as ForceGraphNode).id;
    const tgt = typeof link.target === 'string' ? link.target : (link.target as unknown as ForceGraphNode).id;
    connectedIds.add(src);
    connectedIds.add(tgt);
  }
  const orphanCount = nodes.filter((n) => !connectedIds.has(n.id)).length;
  const n = nodes.length;
  const density = n > 1 ? links.length / (n * (n - 1)) : 0;
  return { nodeCount: n, linkCount: links.length, orphanCount, density };
}

/**
 * filterToNeighborhood returns a sub-graph containing only the focal node
 * and all nodes reachable within `hops` steps.
 */
export function filterToNeighborhood(
  graph: ForceGraphData,
  focalId: string,
  hops = 1,
): ForceGraphData {
  const visited = new Set<string>([focalId]);
  let frontier = new Set<string>([focalId]);

  for (let h = 0; h < hops; h++) {
    const next = new Set<string>();
    for (const link of graph.links) {
      const src = typeof link.source === 'string' ? link.source : (link.source as unknown as ForceGraphNode).id;
      const tgt = typeof link.target === 'string' ? link.target : (link.target as unknown as ForceGraphNode).id;
      if (frontier.has(src) && !visited.has(tgt)) next.add(tgt);
      if (frontier.has(tgt) && !visited.has(src)) next.add(src);
    }
    next.forEach((id) => visited.add(id));
    frontier = next;
  }

  const nodes = graph.nodes.filter((n) => visited.has(n.id));
  const links = graph.links.filter((l) => {
    const src = typeof l.source === 'string' ? l.source : (l.source as unknown as ForceGraphNode).id;
    const tgt = typeof l.target === 'string' ? l.target : (l.target as unknown as ForceGraphNode).id;
    return visited.has(src) && visited.has(tgt);
  });
  return { nodes, links };
}
