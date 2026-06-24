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

/**
 * toForceGraphData converts the raw API GraphData (nodes + edges) into the
 * { nodes, links } shape expected by react-force-graph-2d.
 *
 * Edge endpoints are stored as plain string IDs so the library can resolve
 * them to node objects internally — do NOT pass node objects here.
 */
export function toForceGraphData(graph: GraphData): {
  nodes: ForceGraphNode[];
  links: ForceGraphLink[];
} {
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
    type:   e.type ?? 'wikilink',
  }));

  return { nodes, links };
}
