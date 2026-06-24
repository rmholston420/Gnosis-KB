/**
 * Graph API — typed wrappers around /api/v1/graph endpoints.
 */
import client from './client';
import type { GraphData, GraphStats, GraphPath } from '../types';

/** Get the full graph (all nodes + edges) for visualization. */
export async function getFullGraph(): Promise<GraphData> {
  const { data } = await client.get<GraphData>('/api/v1/graph');
  return data;
}

/** Get ego-graph: a note and its 1-hop neighbors. */
export async function getNeighborhood(noteId: string, hops = 1): Promise<GraphData> {
  const { data } = await client.get<GraphData>(`/api/v1/graph/neighborhood/${noteId}`, {
    params: { hops },
  });
  return data;
}

/** Get shortest path between two notes (NetworkX). */
export async function getPath(fromId: string, toId: string): Promise<GraphPath> {
  const { data } = await client.get<GraphPath>(`/api/v1/graph/path/${fromId}/${toId}`);
  return data;
}

/** Get community clusters (Louvain algorithm). */
export async function getClusters(): Promise<GraphData> {
  const { data } = await client.get<GraphData>('/api/v1/graph/clusters');
  return data;
}

/** Get graph statistics (density, avg degree, orphan count). */
export async function getGraphStats(): Promise<GraphStats> {
  const { data } = await client.get<GraphStats>('/api/v1/graph/stats');
  return data;
}
