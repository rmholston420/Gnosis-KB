import { useQuery } from '@tanstack/react-query';
import api from '../services/api';
import GraphCanvas from '../components/GraphCanvas';
import type { GraphData, GraphStats } from '../types';
import { Loader2 } from 'lucide-react';

export default function GraphPage() {
  const { data: graphData, isLoading } = useQuery<GraphData>({
    queryKey: ['graph'],
    queryFn: () => api.getFullGraph() as Promise<GraphData>,
  });

  const { data: stats } = useQuery<GraphStats>({
    queryKey: ['graph-stats'],
    queryFn: () => api.getGraphStats() as Promise<GraphStats>,
  });

  if (isLoading) {
    return (
      <div className="flex items-center justify-center h-64">
        <Loader2 className="animate-spin text-text-muted" size={24} />
      </div>
    );
  }

  return (
    <div className="flex flex-col h-full">
      <div className="px-4 py-2 border-b border-border flex items-center justify-between flex-shrink-0">
        <h1 className="text-sm font-semibold text-text-primary">Knowledge Graph</h1>
        {stats && (
          <div className="flex gap-4 text-xs text-text-muted">
            <span>{stats.total_notes} notes</span>
            <span>{stats.total_links} links</span>
            <span>{stats.orphan_count} orphans</span>
            <span>density {(stats.density * 100).toFixed(2)}%</span>
          </div>
        )}
      </div>
      {graphData && graphData.nodes.length > 0 ? (
        <div className="flex-1 overflow-hidden">
          <GraphCanvas data={graphData} height="100%" />
        </div>
      ) : (
        <div className="flex items-center justify-center h-64 text-text-muted text-sm">
          No notes in the graph yet. Create some notes and link them with [[wikilinks]].
        </div>
      )}
    </div>
  );
}
