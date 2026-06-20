/**
 * GraphPage
 * =========
 * Two-tab knowledge graph visualisation:
 *   "Wikilinks"        — existing react-force-graph-2d graph of note→note links
 *   "LightRAG Knowledge" — D3 force graph of LightRAG entities + relations,
 *                          coloured by concept cluster, with node-click panel
 *
 * LightRAG tab features
 * ---------------------
 * - Fetches GET /api/v1/graph/lightrag on tab activation (lazy, cached 5 min)
 * - Colours nodes by cluster index using a categorical palette
 * - Hover tooltip shows entity label
 * - Click opens <LightRagNodePanel> with description, relations, source notes
 * - Panel slide-in is CSS-animated (translateX)
 */

import React, { useCallback, useEffect, useRef, useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import { useNavigate } from 'react-router-dom';
import { apiClient } from '@/api/client';
import { Loader2, ZoomIn, ZoomOut, RotateCcw, BarChart2, Network, BookOpen } from 'lucide-react';
import type { ForceGraphMethods } from 'react-force-graph-2d';
import { LightRagNodePanel } from '../components/graph/LightRagNodePanel';
import type { LightRagEntity, LightRagRelation } from '../components/graph/LightRagNodePanel';
import api from '../services/api';

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

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

// Categorical colour palette for LightRAG concept clusters
const CLUSTER_COLORS = [
  '#4f98a3', '#8b5cf6', '#f59e0b', '#10b981', '#ec4899',
  '#3b82f6', '#ef4444', '#06b6d4', '#a78bfa', '#34d399',
];

function clusterColor(cluster?: number) {
  if (cluster === undefined || cluster === null) return CLUSTER_COLORS[0];
  return CLUSTER_COLORS[cluster % CLUSTER_COLORS.length];
}

interface GraphNode {
  id: string;
  title?: string;
  label?: string;
  note_type?: string;
  incoming_link_count?: number;
}
interface GraphEdge   { source: string; target: string; }
interface GraphData   { nodes: GraphNode[]; edges?: GraphEdge[]; links?: GraphEdge[]; }
interface GraphStats  {
  node_count: number; edge_count: number;
  density: number; avg_degree: number; orphan_count: number;
}

interface LightRagNode {
  id: string;
  label: string;
  description?: string;
  cluster?: number;
  source_note_ids?: string[];
  // D3 simulation adds x/y at runtime
  x?: number;
  y?: number;
  vx?: number;
  vy?: number;
}
interface LightRagLink {
  source: string | LightRagNode;
  target: string | LightRagNode;
  label?: string;
  weight?: number;
}
interface LightRagGraphData {
  nodes: LightRagNode[];
  links: LightRagLink[];
  error?: string;
}

const ForceGraph2D = React.lazy(() => import('react-force-graph-2d'));

// ---------------------------------------------------------------------------
// Main component
// ---------------------------------------------------------------------------

type Tab = 'wikilinks' | 'lightrag';

export default function GraphPage() {
  const navigate = useNavigate();
  const fgRef = useRef<ForceGraphMethods | undefined>(undefined);
  const [highlighted, setHighlighted] = useState<string | null>(null);
  const [showStats,   setShowStats]   = useState(false);
  const [activeTab,   setActiveTab]   = useState<Tab>('wikilinks');

  // LightRAG panel state
  const [selectedEntity, setSelectedEntity] = useState<LightRagEntity | null>(null);

  // D3 canvas ref for LightRAG tab
  const lrCanvasRef = useRef<HTMLCanvasElement | null>(null);
  const lrSimRef = useRef<ReturnType<typeof import('d3-force')['forceSimulation']> | null>(null);
  const [tooltip, setTooltip] = useState<{ x: number; y: number; label: string } | null>(null);

  // ---- Wikilinks graph data ------------------------------------------------
  const { data: graphData, isLoading } = useQuery<GraphData>({
    queryKey: ['graph'],
    queryFn: () => apiClient.get<GraphData>('/api/v1/graph/').then((r) => r.data),
    staleTime: 60_000,
  });

  const { data: stats } = useQuery<GraphStats>({
    queryKey: ['graph-stats'],
    queryFn: () => apiClient.get<GraphStats>('/api/v1/graph/stats').then((r) => r.data),
    enabled: showStats,
  });

  // ---- LightRAG graph data (lazy — only fetched when tab is active) --------
  const { data: lrData, isLoading: lrLoading } = useQuery<LightRagGraphData>({
    queryKey: ['lightrag-graph'],
    queryFn: () => api.getLightRagGraph() as Promise<LightRagGraphData>,
    enabled: activeTab === 'lightrag',
    staleTime: 5 * 60_000,
  });

  // ---- Notes list for source-note resolution in panel ---------------------
  const { data: notesData } = useQuery({
    queryKey: ['notes'],
    queryFn: () => api.listNotes({ page_size: 200 }) as Promise<{ items: Array<{ id: string; title: string; folder?: string }> }>,
    staleTime: 60_000,
  });

  const allNotes = notesData?.items ?? [];

  // ---- D3 LightRAG canvas render -------------------------------------------
  useEffect(() => {
    if (activeTab !== 'lightrag' || !lrData || !lrCanvasRef.current) return;
    if (lrData.nodes.length === 0) return;

    // Lazy-load d3-force
    import('d3-force').then((d3) => {
      const canvas = lrCanvasRef.current!;
      const ctx = canvas.getContext('2d')!;
      const W = canvas.width;
      const H = canvas.height;

      // Deep-copy so d3 can mutate nodes safely
      const nodes: LightRagNode[] = lrData.nodes.map((n) => ({ ...n }));
      const links: LightRagLink[] = lrData.links.map((l) => ({ ...l }));

      lrSimRef.current?.stop();

      const sim = d3.forceSimulation<LightRagNode>(nodes)
        .force('link', d3.forceLink<LightRagNode, LightRagLink>(links)
          .id((d) => d.id)
          .distance(80)
        )
        .force('charge', d3.forceManyBody().strength(-120))
        .force('center', d3.forceCenter(W / 2, H / 2))
        .force('collide', d3.forceCollide(18))
        .alpha(0.8)
        .alphaDecay(0.03);

      lrSimRef.current = sim;

      function draw() {
        ctx.clearRect(0, 0, W, H);

        // Links
        ctx.save();
        ctx.strokeStyle = 'rgba(100,120,130,0.35)';
        ctx.lineWidth = 1;
        for (const link of links) {
          const s = link.source as LightRagNode;
          const t = link.target as LightRagNode;
          if (s.x == null || t.x == null) continue;
          ctx.beginPath();
          ctx.moveTo(s.x, s.y!);
          ctx.lineTo(t.x, t.y!);
          ctx.stroke();
        }
        ctx.restore();

        // Nodes
        for (const node of nodes) {
          if (node.x == null) continue;
          ctx.beginPath();
          ctx.arc(node.x, node.y!, 7, 0, Math.PI * 2);
          ctx.fillStyle = clusterColor(node.cluster);
          ctx.fill();
          if (selectedEntity?.id === node.id) {
            ctx.strokeStyle = '#ffffff';
            ctx.lineWidth = 2;
            ctx.stroke();
          }
        }
      }

      sim.on('tick', draw);

      // Click handling
      function handleClick(e: MouseEvent) {
        const rect = canvas.getBoundingClientRect();
        const mx = e.clientX - rect.left;
        const my = e.clientY - rect.top;
        for (const node of nodes) {
          if (node.x == null) continue;
          const dx = mx - node.x;
          const dy = my - node.y!;
          if (Math.sqrt(dx * dx + dy * dy) < 10) {
            setSelectedEntity({
              id: node.id,
              label: node.label,
              description: node.description,
              cluster: node.cluster,
              source_note_ids: node.source_note_ids,
            });
            return;
          }
        }
        // Click on empty area — deselect
        setSelectedEntity(null);
      }

      // Hover tooltip
      function handleMouseMove(e: MouseEvent) {
        const rect = canvas.getBoundingClientRect();
        const mx = e.clientX - rect.left;
        const my = e.clientY - rect.top;
        for (const node of nodes) {
          if (node.x == null) continue;
          const dx = mx - node.x;
          const dy = my - node.y!;
          if (Math.sqrt(dx * dx + dy * dy) < 10) {
            setTooltip({ x: e.clientX, y: e.clientY, label: node.label });
            return;
          }
        }
        setTooltip(null);
      }

      canvas.addEventListener('click', handleClick);
      canvas.addEventListener('mousemove', handleMouseMove);

      return () => {
        sim.stop();
        canvas.removeEventListener('click', handleClick);
        canvas.removeEventListener('mousemove', handleMouseMove);
      };
    });
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [activeTab, lrData]);

  // ---- Wikilinks tab handlers ----------------------------------------------
  const handleNodeClick = useCallback(
    (node: GraphNode) => navigate(`/notes/${node.id}`),
    [navigate],
  );

  const handleNodeHover = useCallback((node: GraphNode | null) => {
    setHighlighted(node?.id ?? null);
  }, []);

  // ---- Shared loading state -----------------------------------------------
  if (isLoading && activeTab === 'wikilinks') {
    return (
      <div className="flex h-screen items-center justify-center">
        <Loader2 className="animate-spin text-blue-500" size={40} />
      </div>
    );
  }

  const fgData = {
    nodes: (graphData?.nodes ?? []).map((n) => ({ ...n })),
    links: ((graphData?.edges ?? graphData?.links) ?? []).map((e) => ({ source: e.source, target: e.target })),
  };

  return (
    <div className="relative h-screen w-full" style={{ background: '#030712' }}>

      {/* Tab bar */}
      <div className="absolute top-0 left-0 right-0 z-20 flex gap-0 border-b border-white/10" style={{ background: 'rgba(3,7,18,0.9)' }}>
        <button
          className={`flex items-center gap-2 px-5 py-3 text-sm font-medium transition-colors ${
            activeTab === 'wikilinks' ? 'text-white border-b-2 border-blue-400' : 'text-gray-400 hover:text-white'
          }`}
          onClick={() => setActiveTab('wikilinks')}
        >
          <Network size={14} /> Wikilinks
        </button>
        <button
          className={`flex items-center gap-2 px-5 py-3 text-sm font-medium transition-colors ${
            activeTab === 'lightrag' ? 'text-white border-b-2 border-purple-400' : 'text-gray-400 hover:text-white'
          }`}
          onClick={() => setActiveTab('lightrag')}
        >
          <BookOpen size={14} /> LightRAG Knowledge
        </button>
      </div>

      {/* ---- WIKILINKS TAB ------------------------------------------------ */}
      {activeTab === 'wikilinks' && (
        <>
          {/* Toolbar */}
          <div className="absolute left-4 z-10 flex gap-2" style={{ top: '56px' }}>
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
              className={`rounded p-2 text-white hover:bg-gray-700 ${ showStats ? 'bg-blue-700' : 'bg-gray-800' }`}
              title="Stats panel" onClick={() => setShowStats((s) => !s)}>
              <BarChart2 size={16} />
            </button>
          </div>

          {showStats && stats && (
            <div className="absolute right-4 z-10 rounded-lg bg-gray-900/90 p-4 text-sm text-white shadow-xl" style={{ top: '56px' }}>
              <h3 className="mb-2 font-semibold">Graph Stats</h3>
              <dl className="space-y-1">
                {([
                  ['Nodes',      stats.node_count],
                  ['Edges',      stats.edge_count],
                  ['Density',    stats.density?.toFixed(4) ?? '—'],
                  ['Avg degree', stats.avg_degree?.toFixed(2) ?? '—'],
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

          <div style={{ paddingTop: '48px', height: '100%' }}>
            <React.Suspense fallback={
              <div className="flex h-screen items-center justify-center text-white">Loading graph…</div>
            }>
              <ForceGraph2D
                ref={fgRef}
                graphData={fgData}
                nodeColor={(node) => {
                  const n = node as GraphNode;
                  return highlighted === n.id ? '#ffffff' : (NODE_COLORS[n.note_type ?? ''] ?? '#6b7280');
                }}
                nodeVal={(node) => {
                  const n = node as GraphNode;
                  return Math.sqrt((n.incoming_link_count ?? 0) + 1) * 3;
                }}
                nodeLabel={(node) => (node as GraphNode).title ?? (node as GraphNode).label ?? ''}
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
        </>
      )}

      {/* ---- LIGHTRAG TAB ------------------------------------------------- */}
      {activeTab === 'lightrag' && (
        <div style={{ paddingTop: '48px', height: '100%', position: 'relative' }}>
          {lrLoading && (
            <div className="flex h-full items-center justify-center">
              <Loader2 className="animate-spin text-purple-400" size={40} />
              <span className="ml-3 text-gray-400">Loading LightRAG graph…</span>
            </div>
          )}

          {!lrLoading && lrData?.error && (
            <div className="flex h-full flex-col items-center justify-center text-gray-400">
              <BookOpen size={48} className="mb-4 opacity-30" />
              <p className="text-lg font-medium">LightRAG graph unavailable</p>
              <p className="mt-1 text-sm opacity-60">{lrData.error}</p>
              <p className="mt-3 text-xs opacity-40">Ingest notes to populate the knowledge graph.</p>
            </div>
          )}

          {!lrLoading && !lrData?.error && lrData?.nodes.length === 0 && (
            <div className="flex h-full flex-col items-center justify-center text-gray-400">
              <BookOpen size={48} className="mb-4 opacity-30" />
              <p className="text-lg font-medium">No knowledge graph yet</p>
              <p className="mt-2 text-sm opacity-60">Use the Notes page → Sync to Graph to ingest your notes.</p>
            </div>
          )}

          {!lrLoading && (lrData?.nodes.length ?? 0) > 0 && (
            <>
              {/* Cluster legend */}
              <div className="absolute bottom-4 left-4 z-10 rounded-lg p-3 text-xs text-white"
                style={{ background: 'rgba(3,7,18,0.8)' }}>
                <p className="mb-1 font-semibold text-gray-300">Clusters</p>
                {CLUSTER_COLORS.slice(0, 5).map((c, i) => (
                  <div key={i} className="flex items-center gap-2">
                    <span className="inline-block h-2.5 w-2.5 rounded-full" style={{ background: c }} />
                    <span className="text-gray-400">Cluster {i + 1}</span>
                  </div>
                ))}
              </div>

              <canvas
                ref={lrCanvasRef}
                width={window.innerWidth}
                height={window.innerHeight - 48}
                style={{ display: 'block', cursor: 'crosshair' }}
              />

              {/* Hover tooltip */}
              {tooltip && (
                <div
                  style={{
                    position: 'fixed',
                    left: tooltip.x + 12,
                    top: tooltip.y - 8,
                    background: 'rgba(15,20,30,0.92)',
                    color: '#e2e8f0',
                    padding: '4px 10px',
                    borderRadius: '6px',
                    fontSize: '12px',
                    pointerEvents: 'none',
                    zIndex: 9000,
                    border: '1px solid rgba(100,120,150,0.3)',
                  }}
                >
                  {tooltip.label}
                </div>
              )}

              {/* Entity detail panel */}
              <LightRagNodePanel
                entity={selectedEntity}
                relations={(lrData?.links ?? []).map((l) => ({
                  source: typeof l.source === 'string' ? l.source : (l.source as LightRagNode).id,
                  target: typeof l.target === 'string' ? l.target : (l.target as LightRagNode).id,
                  label: l.label,
                  weight: l.weight,
                })) as LightRagRelation[]}
                notes={allNotes}
                onClose={() => setSelectedEntity(null)}
                onNavigateToNote={(noteId) => navigate(`/notes/${noteId}`)}
              />
            </>
          )}
        </div>
      )}
    </div>
  );
}
