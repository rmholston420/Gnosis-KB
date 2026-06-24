/**
 * useGraph hooks — TanStack Query wrappers for graph endpoints.
 *
 * Both canonical names and test-expected aliases are exported.
 */
import { useQuery } from '@tanstack/react-query';
import api from '../services/api';
import type { GraphData } from '../types';

/** Fetch the full vault knowledge graph. Canonical name: useFullGraph. */
export function useFullGraph() {
  return useQuery<GraphData>({
    queryKey: ['graph', 'full'],
    queryFn:  () => api.getGraph() as Promise<GraphData>,
    staleTime: 60_000,
  });
}

/** Alias expected by unit tests. */
export const useGraphData = useFullGraph;

/** Fetch the LightRAG-specific graph overlay. */
export function useLightRagGraph() {
  return useQuery<GraphData>({
    queryKey: ['graph', 'lightrag'],
    queryFn:  () => api.getLightRagGraph() as Promise<GraphData>,
    staleTime: 60_000,
  });
}

/** Fetch a single node’s entity summary from the LightRAG graph. */
export function useLightRagNode(nodeId: string) {
  return useQuery({
    queryKey: ['graph', 'lightrag', 'node', nodeId],
    queryFn:  () => api.getLightRagNode(nodeId),
    enabled:  !!nodeId,
  });
}
