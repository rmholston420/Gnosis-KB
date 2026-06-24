/**
 * hooks/useGraph.ts — TanStack Query hooks for graph data.
 */
import { useQuery } from '@tanstack/react-query';
import api from '../services/api';
import type { GraphData, GraphStats } from '../types';

const GRAPH_KEY = 'graph';

export function useFullGraph() {
  return useQuery({
    queryKey: [GRAPH_KEY, 'full'],
    queryFn: () => api.getGraph() as Promise<GraphData>,
  });
}

export const useGraphData = useFullGraph;

export function useLightRagGraph() {
  return useQuery({
    queryKey: [GRAPH_KEY, 'lightrag'],
    queryFn: () => api.getLightRagGraph() as Promise<GraphData>,
  });
}

export function useGraphStats() {
  return useQuery({
    queryKey: [GRAPH_KEY, 'stats'],
    queryFn: async (): Promise<GraphStats> => {
      const data = await (api.getGraph() as Promise<GraphData>);
      const degree = new Map<string, number>();
      for (const e of data.edges) {
        const src = (e as { source_id?: string; source?: string }).source_id ?? (e as { source?: string }).source ?? '';
        const tgt = (e as { target_id?: string; target?: string }).target_id ?? (e as { target?: string }).target ?? '';
        degree.set(src, (degree.get(src) ?? 0) + 1);
        degree.set(tgt, (degree.get(tgt) ?? 0) + 1);
      }
      const sorted = data.nodes
        .map((n) => ({ note_id: (n as { note_id?: string; id?: string }).note_id ?? (n as { id?: string }).id ?? '', title: n.title, degree: degree.get((n as { note_id?: string; id?: string }).note_id ?? (n as { id?: string }).id ?? '') ?? 0 }))
        .sort((a, b) => b.degree - a.degree);
      const totalDeg = [...degree.values()].reduce((s, v) => s + v, 0);
      return {
        total_nodes: data.nodes.length,
        total_edges: data.edges.length,
        avg_degree: data.nodes.length ? totalDeg / data.nodes.length : 0,
        most_connected: sorted.slice(0, 10),
        isolated_count: sorted.filter((n) => n.degree === 0).length,
      };
    },
  });
}
