import React, { useCallback, useRef, useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import { useNavigate } from 'react-router-dom';
import { apiClient } from '@/api/client';
import { Loader2, ZoomIn, ZoomOut, RotateCcw, BarChart2 } from 'lucide-react';
import type { ForceGraphMethods } from 'react-force-graph-2d';

const NODE_COLORS: Record<string, string> = {
  permanent:  '#3b82f6',
  fleeting:   '#94a3b8',
  project:    '#f59e0b',
  area:       '#10b981',
  resource:   '#8b5cf6',
  journal:    '#ec4899',
  moc:        '#ef4444',
  literature: '#06b6d4',
};

interface GraphNode {
  id: string;
  title: string;
  note_type: string;
  incoming_link_count: number;
}

interface GraphEdge { source: string; target: string; }
interface GraphData  { nodes: GraphNode[]; edges: GraphEdge[]; }
interface GraphStats {
  node_count:   number;
  edge_count:   number;
  density:      number;
  avg_degree:   number;
  orphan_count: number;
}

const ForceGraph2D = React.lazy(() => import('react-force-graph-2d'));

export default function GraphPage() {
  const navigate = useNavigate();
  // ForceGraphMethods is the correct ref type for react-force-graph-2d
  const fgRef = useRef<ForceGraphMethods | undefined>(undefined);
  const [highlighted, setHighlighted] = useState<string | null>(null);
  const [showStats,   setShowStats]   = useState(false);

  const { data: graphData, isLoading } = useQuery<GraphData>({
    queryKey: ['graph'],
    queryFn:  () => apiClient.get<GraphData>('/api/v1/graph/').then((r) => r.data),
    staleTime: 60_000,
  });

  const { data: stats } = useQuery<GraphStats>({
    queryKey: ['graph-stats'],
    queryFn:  () => apiClient.get<GraphStats>('/api/v1/graph/stats').then((r) => r.data),
    enabled: showStats,
  });

  const handleNodeClick = useCallback(
    (node: GraphNode) => navigate(`/notes/${node.id}`),
    [navigate],
  );

  const handleNodeHover = useCallback((node: GraphNode | null) => {
    setHighlighted(node?.id ?? null);
  }, []);

  if (isLoading) {
    return (
      <div className="flex h-screen items-center justify-center">
        <Loader2 className="animate-spin text-blue-500" size={40} />
      </div>
    );
  }

  const fgData = {
    nodes: (graphData?.nodes ?? []).map((n) => ({ ...n })),
    links: (graphData?.edges ?? []).map((e) => ({ source: e.source, target: e.target })),
  };

  return (
    <div className="relative h-screen w-full bg-gray-950">
      {/* Toolbar */}
      <div className="absolute left-4 top-4 z-10 flex gap-2">
        <button className="rounded bg-gray-800 p-2 text-white hover:bg-gray-700" title="Zoom in"
          onClick={() => fgRef.current?.zoom(1.5, 400)}>
          <ZoomIn size={16} />
        </button>
        <button className="rounded bg-gray-800 p-2 text-white hover:bg-gray-700" title="Zoom out"
          onClick={() => fgRef.current?.zoom(0.67, 400)}>
          <ZoomOut size={16} />
        </button>
        <button className="rounded bg-gray-800 p-2 text-white hover:bg-gray-700" title="Reset zoom"
          onClick={() => fgRef.current?.zoomToFit(400)}>
          <RotateCcw size={16} />
        </button>
        <button
          className={`rounded p-2 text-white hover:bg-gray-700 ${showStats ? 'bg-blue-700' : 'bg-gray-800'}`}
          title="Stats panel" onClick={() => setShowStats((s) => !s)}>
          <BarChart2 size={16} />
        </button>
      </div>

      {showStats && stats && (
        <div className="absolute right-4 top-4 z-10 rounded-lg bg-gray-900/90 p-4 text-sm text-white shadow-xl">
          <h3 className="mb-2 font-semibold">Graph Stats</h3>
          <dl className="space-y-1">
            {([
              ['Nodes',      stats.node_count],
              ['Edges',      stats.edge_count],
              ['Density',    stats.density.toFixed(4)],
              ['Avg degree', stats.avg_degree.toFixed(2)],
              ['Orphans',    stats.orphan_count],
            ] as [string, string | number][]).map(([k, v]) => (
              <div key={k} className="flex justify-between gap-6">
                <dt className="text-gray-400">{k}</dt>
                <dd className="font-mono">{v}</dd>
              </div>
            ))}
          </dl>
        </div>
      )}

      <div className="absolute bottom-4 left-4 z-10 rounded-lg bg-gray-900/80 p-3 text-xs text-white">
        {Object.entries(NODE_COLORS).map(([type, color]) => (
          <div key={type} className="flex items-center gap-2">
            <span className="inline-block h-2.5 w-2.5 rounded-full" style={{ background: color }} />
            {type}
          </div>
        ))}
      </div>

      <React.Suspense fallback={<div className="flex h-screen items-center justify-center text-white">Loading graph…</div>}>
        <ForceGraph2D
          ref={fgRef}
          graphData={fgData}
          nodeColor={(node) => {
            const n = node as GraphNode;
            return highlighted === n.id ? '#ffffff' : (NODE_COLORS[n.note_type] ?? '#6b7280');
          }}
          nodeVal={(node) => {
            const n = node as GraphNode;
            return Math.sqrt(n.incoming_link_count + 1) * 3;
          }}
          nodeLabel={(node) => (node as GraphNode).title}
          linkWidth={1}
          linkDirectionalArrowLength={3}
          linkDirectionalArrowRelPos={1}
          onNodeClick={handleNodeClick as (node: object) => void}
          onNodeHover={handleNodeHover as (node: object | null) => void}
          enableNodeDrag
          cooldownTicks={100}
          backgroundColor="#030712"
        />
      </React.Suspense>
    </div>
  );
}
