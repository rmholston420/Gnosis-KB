/**
 * useGraph — TanStack Query hooks for graph data.
 */
import { useQuery } from '@tanstack/react-query';
import {
  getFullGraph,
  getNeighborhood,
  getGraphStats,
  getClusters,
  getGraphNode,
  getLightRagGraph,
  getGraphEntities,
} from '../api/graph';
import type { GraphData, GraphNode, GraphEdge, GraphStats } from '../types';

/**
 * useGraphData / useGraph — fetches the full knowledge graph.
 * Uses getFullGraph so the vi.mock('../../api/graph') in tests
 * intercepts the call correctly.
 */
export function useGraphData() {
  return useQuery({
    queryKey: ['graph'],
    queryFn: () => getFullGraph() as Promise<GraphData>,
    staleTime: 60_000,
  });
}

/** Alias kept for backwards-compat with existing call-sites. */
export const useGraph = useGraphData;

export function useFullGraph() {
  return useQuery({
    queryKey: ['graph', 'full'],
    queryFn: () => getFullGraph(),
    staleTime: 60_000,
  });
}

export function useGraphNeighborhood(nodeId: string | null) {
  return useQuery({
    queryKey: ['graph', 'neighborhood', nodeId],
    queryFn: () => getNeighborhood(nodeId!),
    enabled: !!nodeId,
    staleTime: 30_000,
  });
}

export function useGraphStats() {
  return useQuery<GraphStats>({
    queryKey: ['graph', 'stats'],
    queryFn: () => getGraphStats() as Promise<GraphStats>,
    staleTime: 120_000,
  });
}

export function useGraphClusters() {
  return useQuery({
    queryKey: ['graph', 'clusters'],
    queryFn: () => getClusters(),
    staleTime: 120_000,
  });
}

export function useGraphNode(nodeId: string | null) {
  return useQuery({
    queryKey: ['graph', 'node', nodeId],
    queryFn: () => getGraphNode(nodeId!),
    enabled: !!nodeId,
    staleTime: 30_000,
  });
}

export function useLightRagGraph() {
  return useQuery({
    queryKey: ['graph', 'lightrag'],
    queryFn: () => getLightRagGraph(),
    staleTime: 60_000,
  });
}

export function useGraphEntities(type?: string) {
  return useQuery({
    queryKey: ['graph', 'entities', type],
    queryFn: () => getGraphEntities(type),
    staleTime: 60_000,
  });
}

export type { GraphData, GraphNode, GraphEdge };
