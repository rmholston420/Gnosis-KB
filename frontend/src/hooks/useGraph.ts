/**
 * useGraph — TanStack Query hooks for graph data.
 *
 * Imports graph functions from services/api (the canonical client).
 * getFullGraph, getNeighborhood, getGraphStats, getClusters are all
 * defined there; no separate api/graph module is needed.
 */
import { useQuery } from '@tanstack/react-query';
import {
  getGraph,
  getFullGraph,
  getNeighborhood,
  getGraphStats,
  getClusters,
  getGraphNode,
  getLightRagGraph,
  getGraphEntities,
} from '../services/api';
import type { GraphData, GraphNode, GraphEdge, GraphStats } from '../types';

export function useGraph() {
  return useQuery({
    queryKey: ['graph'],
    queryFn:  async () => {
      const raw = await getGraph();
      return raw as GraphData;
    },
    staleTime: 60_000,
  });
}

/** Alias — tests import useGraphData */
export const useGraphData = useGraph;

export function useFullGraph() {
  return useQuery({
    queryKey: ['graph', 'full'],
    queryFn:  () => getFullGraph(),
    staleTime: 60_000,
  });
}

export function useGraphNeighborhood(nodeId: string | null) {
  return useQuery({
    queryKey: ['graph', 'neighborhood', nodeId],
    queryFn:  () => getNeighborhood(nodeId!),
    enabled:  !!nodeId,
    staleTime: 30_000,
  });
}

export function useGraphStats() {
  // Explicit type parameter so TanStack Query infers data as GraphStats
  // (which includes optional aliases total_notes and orphan_count used by tests).
  return useQuery<GraphStats>({
    queryKey: ['graph', 'stats'],
    queryFn:  () => getGraphStats() as Promise<GraphStats>,
    staleTime: 120_000,
  });
}

export function useGraphClusters() {
  return useQuery({
    queryKey: ['graph', 'clusters'],
    queryFn:  () => getClusters(),
    staleTime: 120_000,
  });
}

export function useGraphNode(nodeId: string | null) {
  return useQuery({
    queryKey: ['graph', 'node', nodeId],
    queryFn:  () => getGraphNode(nodeId!),
    enabled:  !!nodeId,
    staleTime: 30_000,
  });
}

export function useLightRagGraph() {
  return useQuery({
    queryKey: ['graph', 'lightrag'],
    queryFn:  () => getLightRagGraph(),
    staleTime: 60_000,
  });
}

export function useGraphEntities(type?: string) {
  return useQuery({
    queryKey: ['graph', 'entities', type],
    queryFn:  () => getGraphEntities(type),
    staleTime: 60_000,
  });
}

// Typed convenience aliases
export type { GraphData, GraphNode, GraphEdge };
