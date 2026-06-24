/**
 * api/graph.ts — typed wrappers for the knowledge graph endpoints.
 *
 * Used by:
 *   GraphPage   (LightRAG tab entity list + health check)
 *   graphUtils  (type imports)
 */

export interface GraphEntitySummary {
  id:          string;
  label:       string;
  type?:       string;
  description?: string;
}

export interface LightRagGraphHealth {
  node_count:     number;
  edge_count:     number;
  is_empty:       boolean;
  last_updated?:  string;
}

const BASE = '/api/v1';

/** Fetch the full wikilink graph (nodes + edges). */
export async function fetchGraph(): Promise<{ nodes: unknown[]; edges: unknown[] }> {
  const res = await fetch(`${BASE}/graph/full`);
  if (!res.ok) throw new Error(`Graph fetch failed: ${res.status}`);
  return res.json() as Promise<{ nodes: unknown[]; edges: unknown[] }>;
}

/** Fetch LightRAG entity summaries for the entity-filter panel. */
export async function getGraphEntities(): Promise<{ entities: GraphEntitySummary[] }> {
  const res = await fetch(`${BASE}/graph/entities`);
  if (!res.ok) throw new Error(`Entities fetch failed: ${res.status}`);
  return res.json() as Promise<{ entities: GraphEntitySummary[] }>;
}

/** Fetch LightRAG knowledge-graph health / stats. */
export async function getLightRagGraph(): Promise<LightRagGraphHealth> {
  const res = await fetch(`${BASE}/graph/lightrag`);
  if (!res.ok) throw new Error(`LightRAG graph fetch failed: ${res.status}`);
  return res.json() as Promise<LightRagGraphHealth>;
}
