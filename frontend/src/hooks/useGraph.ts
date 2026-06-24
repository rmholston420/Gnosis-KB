/**
 * hooks/useGraph.ts — TanStack Query hooks for graph data.
 */
import { useQuery } from '@tanstack/react-query';
import { graphApi } from '../api/graph';
import type { GraphData, GraphStats } from '../types';

const GRAPH_KEY = 'graph';

export function useFullGraph() {
  return useQuery({
    queryKey: [GRAPH_KEY, 'full'],
    queryFn:  (): Promise<GraphData> => graphApi.getFullGraph(),
  });
}

/** Named alias used by GraphView2D and tests */
export const useGraphData = useFullGraph;

export function useLightRagGraph() {
  return useQuery({
    queryKey: [GRAPH_KEY, 'lightrag'],
    queryFn:  (): Promise<GraphData> => graphApi.getLightRagGraph(),
  });
}

/**
 * Graph statistics — derived client-side from the full graph if no
 * dedicated backend endpoint exists.
 */
export function useGraphStats() {
  return useQuery({
    queryKey: [GRAPH_KEY, 'stats'],
    queryFn:  async (): Promise<GraphStats> => {
      const data = await graphApi.getFullGraph();
      const degree = new Map<string, number>();
      for (const e of data.edges) {
        const src = e.source_id;
        const tgt = e.target_id;
        degree.set(src, (degree.get(src) ?? 0) + 1);
        degree.set(tgt, (degree.get(tgt) ?? 0) + 1);
      }
      const sorted = data.nodes
        .map(n => ({ note_id: n.note_id, title: n.title, degree: degree.get(n.note_id) ?? 0 }))
        .sort((a, b) => b.degree - a.degree);
      const totalDeg = [...degree.values()].reduce((s, v) => s + v, 0);
      return {
        total_nodes:    data.nodes.length,
        total_edges:    data.edges.length,
        avg_degree:     data.nodes.length ? totalDeg / data.nodes.length : 0,
        most_connected: sorted.slice(0, 10),
        isolated_count: sorted.filter(n => n.degree === 0).length,
      };
    },
  });
}
