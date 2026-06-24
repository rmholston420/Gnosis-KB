/**
 * api/graph.ts — typed API client for graph endpoints.
 */
import type { GraphData, GraphEntitySummary } from '../types';

const BASE = (import.meta as unknown as { env: Record<string, string> }).env?.VITE_API_URL ?? '';

async function req<T>(path: string): Promise<T> {
  const res = await fetch(`${BASE}${path}`, {
    headers: { 'Content-Type': 'application/json' },
  });
  if (!res.ok) throw new Error(`Graph API ${res.status}: ${path}`);
  return res.json() as Promise<T>;
}

export const graphApi = {
  /** Full note-link graph (nodes + edges). */
  getFullGraph:      () => req<GraphData>('/api/graph'),

  /** LightRAG knowledge graph (nodes + edges). */
  getLightRagGraph:  () => req<GraphData>('/api/lightrag/graph'),

  /** Named entity summaries from LightRAG. */
  getGraphEntities:  () => req<GraphEntitySummary[]>('/api/lightrag/entities'),
};

export default graphApi;
