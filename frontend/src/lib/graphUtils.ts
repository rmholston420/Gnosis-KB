/**
 * graphUtils — utilities for transforming raw API graph data into
 * the shape expected by GraphView2D / GraphCanvas.
 *
 * Also exports nodeColor, nodeVal, NODE_COLORS, toForceGraph,
 * toForceGraphData, clusterColor, getNeighbours, computeGraphStats,
 * and filterToNeighborhood so that GraphPage, GraphView2D,
 * NodeDetailOverlay, VaultTree, SearchResults, and tests can import
 * them without reaching into separate modules.
 */
import type { GraphNode, GraphEdge, GraphData, GraphStats } from '../types';

export interface NormalizedNode {
  id:       string;
  title:    string;
  type:     string;
  status?:  string;
  x?:       number;
  y?:       number;
  cluster?: number;
  incoming_link_count?: number;
  outgoing_link_count?: number;
  tag_count?:  number;
  word_count?: number;
  tags?:    string[];
  folder?:  string;
}

export interface NormalizedEdge {
  source:    string;
  target:    string;
  type:      string;
  link_text?: string;
  weight?:   number;
}

// ── Color palette ─────────────────────────────────────────────────────────────

export const NODE_COLORS: Record<string, string> = {
  permanent:  '#4f98a3',
  fleeting:   '#bb653b',
  project:    '#6daa45',
  area:       '#d19900',
  resource:   '#5591c7',
  journal:    '#a86fdf',
  moc:        '#dd6974',
  literature: '#fdab43',
  map:        '#4f98a3',
  orphan:     '#bb653b',
  default:    '#4f98a3',
};

/** Return a display color for a graph node based on its note_type. */
export function nodeColor(node: GraphNode | { type?: string; note_type?: string }): string {
  const t = ('note_type' in node ? node.note_type : undefined) ?? ('type' in node ? node.type : undefined) ?? 'default';
  return NODE_COLORS[t as string] ?? NODE_COLORS.default;
}

/** Return a size value for a graph node based on its incoming link count. */
export function nodeVal(node: GraphNode | { incoming_link_count?: number }): number {
  return Math.max(1, ('incoming_link_count' in node ? node.incoming_link_count : undefined) ?? 1);
}

/** Return a cluster color from the NODE_COLORS palette by index. */
export function clusterColor(idx?: number): string {
  const palette = Object.values(NODE_COLORS);
  return palette[(idx ?? 0) % palette.length];
}

// ── Normalizers ───────────────────────────────────────────────────────────────

export function normalizeNode(n: GraphNode): NormalizedNode {
  return {
    id:                  n.note_id ?? '',
    title:               n.title  ?? '',
    type:                (n.note_type ?? n.type ?? 'permanent') as string,
    status:              n.status,
    x:                   n.x,
    y:                   n.y,
    cluster:             n.cluster_id,
    incoming_link_count: n.incoming_link_count,
    outgoing_link_count: n.outgoing_link_count,
    tag_count:           n.tag_count,
    word_count:          n.word_count,
    tags:                n.tags,
    folder:              n.folder,
  };
}

export function normalizeEdge(e: GraphEdge): NormalizedEdge {
  return {
    source:    e.source_id ?? (e.source ?? ''),
    target:    e.target_id ?? (e.target ?? ''),
    type:      (e.link_type ?? 'wikilink') as string,
    link_text: e.link_text,
    weight:    e.weight,
  };
}

export function normalizeGraph(raw: GraphData): { nodes: NormalizedNode[]; edges: NormalizedEdge[] } {
  return {
    nodes: (raw.nodes ?? []).map(normalizeNode),
    edges: (raw.edges ?? []).map(normalizeEdge),
  };
}

// ── Force-graph shape ─────────────────────────────────────────────────────────

export interface ForceGraphShape {
  nodes: NormalizedNode[];
  links: NormalizedEdge[];
}

/** Convert raw GraphData to the { nodes, links } shape expected by react-force-graph. */
export function toForceGraph(raw: GraphData): ForceGraphShape {
  const { nodes, edges } = normalizeGraph(raw);
  return { nodes, links: edges };
}

/** Alias — some callers import toForceGraphData. */
export const toForceGraphData = toForceGraph;

// ── Graph analysis ────────────────────────────────────────────────────────────

/** Compute a simple degree map from edges. */
export function computeDegrees(edges: NormalizedEdge[]): Record<string, number> {
  const deg: Record<string, number> = {};
  for (const e of edges) {
    deg[e.source] = (deg[e.source] ?? 0) + 1;
    deg[e.target] = (deg[e.target] ?? 0) + 1;
  }
  return deg;
}

/** Return the immediate neighbours of a node (1-hop). */
export function getNeighbours(
  nodeId: string,
  nodes: NormalizedNode[],
  edges: NormalizedEdge[],
): NormalizedNode[] {
  const neighbourIds = new Set<string>();
  for (const e of edges) {
    if (e.source === nodeId) neighbourIds.add(e.target);
    if (e.target === nodeId) neighbourIds.add(e.source);
  }
  return nodes.filter((n) => neighbourIds.has(n.id));
}

/** Compute summary statistics for a normalised graph. */
export function computeGraphStats(
  nodes: NormalizedNode[],
  edges: NormalizedEdge[],
): Pick<GraphStats, 'total_nodes' | 'total_edges' | 'avg_degree' | 'isolated_count'> {
  const degrees = computeDegrees(edges);
  const totalDeg = Object.values(degrees).reduce((s, d) => s + d, 0);
  const isolatedCount = nodes.filter((n) => !(n.id in degrees)).length;
  return {
    total_nodes:    nodes.length,
    total_edges:    edges.length,
    avg_degree:     nodes.length > 0 ? totalDeg / nodes.length : 0,
    isolated_count: isolatedCount,
  };
}

/**
 * Return the subgraph consisting of a focal node and all its 1-hop neighbours.
 */
export function filterToNeighborhood(
  focalId: string,
  nodes: NormalizedNode[],
  edges: NormalizedEdge[],
): { nodes: NormalizedNode[]; edges: NormalizedEdge[] } {
  const neighbours = getNeighbours(focalId, nodes, edges);
  const ids = new Set([focalId, ...neighbours.map((n) => n.id)]);
  return {
    nodes: nodes.filter((n) => ids.has(n.id)),
    edges: edges.filter((e) => ids.has(e.source) && ids.has(e.target)),
  };
}
