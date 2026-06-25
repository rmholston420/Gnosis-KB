/**
 * graphUtils — utilities for transforming raw API graph data into
 * the shape expected by GraphView2D / GraphCanvas.
 */
import type { GraphNode, GraphEdge, GraphData } from '../types';

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

/** Compute a simple degree map from edges. */
export function computeDegrees(edges: NormalizedEdge[]): Record<string, number> {
  const deg: Record<string, number> = {};
  for (const e of edges) {
    deg[e.source] = (deg[e.source] ?? 0) + 1;
    deg[e.target] = (deg[e.target] ?? 0) + 1;
  }
  return deg;
}
