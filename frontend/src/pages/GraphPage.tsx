/**
 * GraphPage
 * =========
 * Two-tab knowledge graph visualisation:
 *   "Wikilinks"          — react-force-graph-2d graph of note→note links
 *   "LightRAG Knowledge" — D3 force graph of LightRAG
 *
 * Slice 22 additions:
 *  - LightRAG tab: entity sidebar list
 *     • Search filter
 *     • Cluster colour dot per entity
 *     • Click row → opens existing LightRagNodePanel
 *     • Entity count badge in panel header
 * - Improved empty state: "Sync Vault" button triggers vault sync 
 *   instead of the old "Ingest All"
 */

import React, { useCallback, useEffect, useRef, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { useQuery, useMutation } from '@tanstack/react-query';
import {
  Network,
  ZoomIn,
  ZoomOut,
  Maximize2,
  RefreshCw,
  Search,
  Layers,
  Info,
  Database,
} from 'lucide-react';
import type { ForceGraphMethods } from 'react-force-graph-2d';
import api from '../services/api';
import type { LightRagEntity, LightRagRelation } from '../components/graph/LightRagNodePanel';
import { LightRagNodePanel } from '../components/graph/LightRagNodePanel';
import type { GraphEntitySummary } from '../services/api';
import type { GraphData } from '../types';

const ForceGraph2D = React.lazy(() => import('react-force-graph-2d'));

// ---------- helpers ---------------------------------------------------------

const CLUSTER_COLORS = [
  '#4f9cf9', '#f97316', '#22c55e', '#a855f7',
  '#ec4899', '#14b8a6', '#f59e0b', '#6366f1',
];

function clusterColor(cluster?: number): string {
  if (cluster == null) return '#9ca3af';
  return CLUSTER_COLORS[cluster % CLUSTER_COLORS.length];
}

type NodeObject = {
  id: string;
  title?: string;
  note_type?: string;
  status?: string;
  folder?: string;
  val?: number;
  color?: string;
};

type LinkObject = {
  source: string | NodeObject;
  target: string | NodeObject;
  link_text?: string;
};

function nodeId(n: string | NodeObject): string {
  return typeof n === 'string' ? n : n.id;
}

// ---------------------------------------------------------------------------

export default function GraphPage() {
  const navigate = useNavigate();

  // ---- Tab state ---------------------------------------------------------
  const [activeTab, setActiveTab] = useState<'wikilinks' | 'lightrag'>('wikilinks');

  // ---- Wikilinks graph state --------------------------------------------
  const [search,       setSearch]       = useState('');
  const [hoveredNode,  setHoveredNode]  = useState<NodeObject | null>(null);
  const [selectedNode, setSelectedNode] = useState<NodeObject | null>(null);

  // ---- LightRAG state ---------------------------------------------------
  const [lrSearch,         setLrSearch]         = useState('');
  const [lrSelectedEntity, setLrSelectedEntity] = useState<LightRagEntity | null>(null);
  const [lrRelations,      setLrRelations]      = useState<LightRagRelation[]>([]);
  const [entitySearch,     setEntitySearch]     = useState('');

  const fgRef    = useRef<ForceGraphMethods | undefined>(undefined);
  const canvasRef = useRef<HTMLCanvasElement | null>(null);

  const lrSimRef    = useRef<any>(null);
  const lrCanvasRef = useRef<HTMLCanvasElement | null>(null);
  const animFrameRef = useRef<number | null>(null);

  // ---- Queries -----------------------------------------------------------
  const { data: graphData, isLoading: graphLoading, refetch: refetchGraph } =
    useQuery<GraphData>({
      queryKey: ['graph'],
      queryFn:  () => api.getFullGraph() as Promise<GraphData>,
      staleTime: 30_000,
    });

  const { data: lrGraphData, isLoading: lrLoading, refetch: refetchLr } =
    useQuery({
      queryKey: ['lr-graph'],
      queryFn:  () =>
        (api as any).apiClient
          ? (api as any).apiClient.get('/api/v1/graph/lightrag').then((r: any) => r.data)
          : Promise.resolve(null),
      staleTime: 60_000,
      enabled: activeTab === 'lightrag',
    });

  const { data: entitiesData, isLoading: entitiesLoading } =
    useQuery({
      queryKey: ['graph-entities'],
      queryFn:  () => api.getGraphEntities().then((d: any) => (d?.entities ?? d) as GraphEntitySummary[]),
      staleTime: 60_000,
      enabled: activeTab === 'lightrag',
    });

  // ---- Mutations ---------------------------------------------------------
  const syncMutation = useMutation({
    mutationFn: () =>
      (api as any).syncVault
        ? (api as any).syncVault()
        : Promise.resolve(),
  });

  // ---- Zoom helpers (wikilinks tab) --------------------------------------
  const handleZoomIn  = () => fgRef.current?.zoom(1.5, 300);
  const handleZoomOut = () => fgRef.current?.zoom(0.75, 300);
  const handleFit     = () => fgRef.current?.zoomToFit(400, 40);

  // ---- LightRAG node click ----------------------------------------------
  const apiClient = (api as any).apiClient;

  const handleLrNodeClick = useCallback(
    async (nodeId: string) => {
      if (!apiClient) return;
      try {
        const [entityRes, relRes] = await Promise.all([
          apiClient.get(`/api/v1/graph/entities/${encodeURIComponent(nodeId)}`),
          apiClient.get(
            `/api/v1/graph/entities/${encodeURIComponent(nodeId)}/relations`
          ),
        ]);
        setLrSelectedEntity(entityRes.data);
        setLrRelations(relRes.data.relations ?? []);
      } catch (err) {
        console.error('LR node fetch failed', err);
      }
    },
    [apiClient]
  );

  // ---- Wikilinks graph data prep ----------------------------------------
  const nodes: NodeObject[] = (graphData?.nodes ?? []).map((n) => ({
    id:        n.id,
    title:     n.title,
    note_type: n.note_type,
    status:    n.status,
    folder:    n.folder,
    val:       Math.max(1, Math.sqrt(n.incoming_link_count + n.outgoing_link_count + 1)),
    color:     n.status === 'evergreen' ? '#22c55e'
             : n.note_type === 'map'    ? '#f97316'
             : '#4f9cf9',
  }));

  const links: LinkObject[] = (graphData?.edges ?? []).map((e) => ({
    source:    e.source,
    target:    e.target,
    link_text: e.link_text,
  }));

  const filteredNodes = search
    ? nodes.filter((n) => n.title?.toLowerCase().includes(search.toLowerCase()))
    : nodes;
  const filteredNodeIds = new Set(filteredNodes.map((n) => n.id));
  const filteredLinks = search
    ? links.filter(
        (l) => filteredNodeIds.has(nodeId(l.source)) && filteredNodeIds.has(nodeId(l.target))
      )
    : links;

  // ---- LightRAG canvas render -------------------------------------------
  useEffect(() => {
    if (activeTab !== 'lightrag' || !lrGraphData || !lrCanvasRef.current) return;

    const canvas = lrCanvasRef.current;
    const ctx = canvas.getContext('2d');
    if (!ctx) return;

    // Cancel previous animation
    if (animFrameRef.current) cancelAnimationFrame(animFrameRef.current);

    const w = canvas.width;
    const h = canvas.height;

    const lrNodes: any[] = (lrGraphData.entities ?? []).map((e: any) => ({
      id: e.id,
      label: e.label,
      cluster: e.cluster,
      x: Math.random() * w,
      y: Math.random() * h,
      vx: 0,
      vy: 0,
    }));

    const lrLinks: any[] = (lrGraphData.relations ?? []).map((r: any) => ({
      source: r.source,
      target: r.target,
      label:  r.label,
    }));

    // Simple force simulation (no d3 dep — manual Euler integration)
    function tick() {
      // Repulsion
      for (let i = 0; i < lrNodes.length; i++) {
        for (let j = i + 1; j < lrNodes.length; j++) {
          const dx = lrNodes[j].x - lrNodes[i].x;
          const dy = lrNodes[j].y - lrNodes[i].y;
          const dist = Math.sqrt(dx * dx + dy * dy) || 1;
          const force = 800 / (dist * dist);
          lrNodes[i].vx -= (force * dx) / dist;
          lrNodes[i].vy -= (force * dy) / dist;
          lrNodes[j].vx += (force * dx) / dist;
          lrNodes[j].vy += (force * dy) / dist;
        }
      }
      // Attraction (links)
      const nodeMap = new Map(lrNodes.map((n) => [n.id, n]));
      for (const link of lrLinks) {
        const s = nodeMap.get(link.source);
        const t = nodeMap.get(link.target);
        if (!s || !t) continue;
        const dx = t.x - s.x;
        const dy = t.y - s.y;
        const dist = Math.sqrt(dx * dx + dy * dy) || 1;
        const force = (dist - 80) * 0.01;
        s.vx += (force * dx) / dist;
        s.vy += (force * dy) / dist;
        t.vx -= (force * dx) / dist;
        t.vy -= (force * dy) / dist;
      }
      // Centre gravity
      for (const n of lrNodes) {
        n.vx += (w / 2 - n.x) * 0.002;
        n.vy += (h / 2 - n.y) * 0.002;
        // Damping
        n.vx *= 0.85;
        n.vy *= 0.85;
        n.x += n.vx;
        n.y += n.vy;
      }
    }

    function draw() {
      ctx!.clearRect(0, 0, w, h);
      // Draw links
      ctx!.strokeStyle = '#374151';
      ctx!.lineWidth = 1;
      const nodeMap = new Map(lrNodes.map((n: any) => [n.id, n]));
      for (const link of lrLinks) {
        const s = nodeMap.get(link.source);
        const t = nodeMap.get(link.target);
        if (!s || !t) continue;
        ctx!.beginPath();
        ctx!.moveTo(s.x, s.y);
        ctx!.lineTo(t.x, t.y);
        ctx!.stroke();
      }
      // Draw nodes
      for (const n of lrNodes) {
        const color = clusterColor(n.cluster);
        ctx!.beginPath();
        ctx!.arc(n.x, n.y, 5, 0, Math.PI * 2);
        ctx!.fillStyle = color;
        ctx!.fill();
      }
    }

    let frame = 0;
    function loop() {
      if (frame < 200) tick();
      draw();
      frame++;
      animFrameRef.current = requestAnimationFrame(loop);
    }
    animFrameRef.current = requestAnimationFrame(loop);

    // Click handler
    const handleClick = (ev: MouseEvent) => {
      const rect = canvas.getBoundingClientRect();
      const mx = ev.clientX - rect.left;
      const my = ev.clientY - rect.top;
      for (const n of lrNodes) {
        const dx = n.x - mx;
        const dy = n.y - my;
        if (Math.sqrt(dx * dx + dy * dy) < 8) {
          void handleLrNodeClick(n.id);
          break;
        }
      }
    };
    canvas.addEventListener('click', handleClick);

    lrSimRef.current = lrNodes;

    return () => {
      if (animFrameRef.current) cancelAnimationFrame(animFrameRef.current);
      canvas.removeEventListener('click', handleClick);
    };
  }, [activeTab, lrGraphData, handleLrNodeClick]);

  // ---- Entity list -------------------------------------------------------
  const allEntities: GraphEntitySummary[] = (entitiesData as GraphEntitySummary[] | undefined) ?? [];
  const filteredEntities = allEntities.filter(
    (e) => !entitySearch || e.id.toLowerCase().includes(entitySearch.toLowerCase())
      || e.label?.toLowerCase().includes(entitySearch.toLowerCase())
  );

  // ---- Render ------------------------------------------------------------
  return (
    <div className="flex h-full flex-col bg-bg-primary text-text-primary overflow-hidden">

      {/* ── Header ──────────────────────────────────────────────────── */}
      <div className="flex items-center justify-between gap-3 border-b border-border-default px-4 py-3 flex-shrink-0">
        <div className="flex items-center gap-2">
          <Network size={18} className="text-accent-teal" />
          <h1 className="text-sm font-semibold">Knowledge Graph</h1>
          {graphData && (
            <span className="rounded-full bg-bg-tertiary px-2 py-0.5 text-xs text-text-muted">
              {graphData.nodes.length} nodes · {graphData.edges.length} edges
            </span>
          )}
        </div>
        <div className="flex items-center gap-2">
          <button
            onClick={() => { void refetchGraph(); void refetchLr(); }}
            className="flex items-center gap-1 rounded px-2 py-1 text-xs text-text-muted hover:bg-bg-elevated transition-colors"
          >
            <RefreshCw size={12} /> Refresh
          </button>
        </div>
      </div>

      {/* ── Tabs ────────────────────────────────────────────────────── */}
      <div className="flex border-b border-border-default flex-shrink-0">
        {(['wikilinks', 'lightrag'] as const).map((tab) => (
          <button
            key={tab}
            onClick={() => setActiveTab(tab)}
            className={`flex items-center gap-1.5 px-4 py-2 text-xs font-medium transition-colors border-b-2 ${
              activeTab === tab
                ? 'border-accent-teal text-accent-teal'
                : 'border-transparent text-text-muted hover:text-text-primary'
            }`}
          >
            {tab === 'wikilinks' ? <Network size={13} /> : <Database size={13} />}
            {tab === 'wikilinks' ? 'Wikilinks' : 'LightRAG Knowledge'}
          </button>
        ))}
      </div>

      {/* ── Wikilinks tab ───────────────────────────────────────────── */}
      {activeTab === 'wikilinks' && (
        <div className="flex flex-1 min-h-0 overflow-hidden">

          {/* Graph canvas */}
          <div className="relative flex-1 min-w-0 overflow-hidden bg-bg-primary">

            {/* Toolbar */}
            <div className="absolute top-3 left-3 z-10 flex gap-1.5">
              <div className="relative">
                <Search size={13} className="absolute left-2 top-1/2 -translate-y-1/2 text-text-faint" />
                <input
                  value={search}
                  onChange={(e) => setSearch(e.target.value)}
                  placeholder="Filter nodes…"
                  className="w-44 rounded bg-bg-secondary pl-7 pr-3 py-1 text-xs focus:outline-none border border-border-default"
                />
              </div>
              <button onClick={handleZoomIn}  className="icon-btn"><ZoomIn  size={13} /></button>
              <button onClick={handleZoomOut} className="icon-btn"><ZoomOut size={13} /></button>
              <button onClick={handleFit}     className="icon-btn"><Maximize2 size={13} /></button>
            </div>

            {graphLoading && (
              <div className="absolute inset-0 flex items-center justify-center">
                <RefreshCw size={20} className="animate-spin text-text-muted" />
              </div>
            )}

            {!graphLoading && nodes.length === 0 && (
              <div className="absolute inset-0 flex flex-col items-center justify-center gap-3 text-text-muted">
                <Network size={40} className="opacity-30" />
                <p className="text-sm">No notes in the graph yet.</p>
                <button
                  onClick={() => void syncMutation.mutate()}
                  disabled={syncMutation.isPending}
                  className="flex items-center gap-1.5 rounded bg-accent-teal/10 px-3 py-1.5 text-xs text-accent-teal hover:bg-accent-teal/20 transition-colors disabled:opacity-50"
                >
                  <RefreshCw size={12} className={syncMutation.isPending ? 'animate-spin' : ''} />
                  Sync Vault
                </button>
              </div>
            )}

            {!graphLoading && nodes.length > 0 && (
              <React.Suspense fallback={<div className="flex h-full items-center justify-center"><RefreshCw size={20} className="animate-spin text-text-muted" /></div>}>
                <ForceGraph2D
                  ref={fgRef}
                  graphData={{ nodes: filteredNodes, links: filteredLinks }}
                  nodeId="id"
                  nodeLabel="title"
                  nodeColor={(n: any) => (n as NodeObject).color ?? '#4f9cf9'}
                  nodeVal={(n: any) => (n as NodeObject).val ?? 1}
                  linkColor={() => '#374151'}
                  linkWidth={1}
                  backgroundColor="transparent"
                  onNodeClick={(n: any) => {
                    const node = n as NodeObject;
                    setSelectedNode(node);
                    navigate(`/notes/${node.id}`);
                  }}
                  onNodeHover={(n: any) => setHoveredNode(n as NodeObject | null)}
                  width={undefined}
                  height={undefined}
                />
              </React.Suspense>
            )}
          </div>

          {/* Selected node info panel */}
          {(selectedNode || hoveredNode) && (
            <div className="w-64 border-l border-border-default bg-bg-secondary p-4 flex-shrink-0 overflow-y-auto">
              {(() => {
                const n = selectedNode ?? hoveredNode!;
                return (
                  <>
                    <div className="flex items-start justify-between gap-2 mb-3">
                      <h3 className="text-sm font-semibold leading-tight">{n.title}</h3>
                      <button onClick={() => { setSelectedNode(null); setHoveredNode(null); }}
                        className="text-text-faint hover:text-text-primary mt-0.5">&#x2715;</button>
                    </div>
                    <dl className="space-y-2 text-xs">
                      {n.note_type && (
                        <div><dt className="text-text-faint">Type</dt><dd className="text-text-primary capitalize">{n.note_type}</dd></div>
                      )}
                      {n.status && (
                        <div><dt className="text-text-faint">Status</dt><dd className="text-text-primary capitalize">{n.status}</dd></div>
                      )}
                      {n.folder && (
                        <div><dt className="text-text-faint">Folder</dt><dd className="text-text-primary">{n.folder}</dd></div>
                      )}
                    </dl>
                    <button
                      onClick={() => navigate(`/notes/${n.id}`)}
                      className="mt-4 w-full rounded bg-accent-teal/10 py-1.5 text-xs text-accent-teal hover:bg-accent-teal/20 transition-colors"
                    >
                      Open Note
                    </button>
                  </>
                );
              })()}
            </div>
          )}
        </div>
      )}

      {/* ── LightRAG tab ────────────────────────────────────────────── */}
      {activeTab === 'lightrag' && (
        <div className="flex flex-1 min-h-0 overflow-hidden">

          {/* Canvas area */}
          <div className="relative flex-1 min-w-0 overflow-hidden bg-bg-primary">

            {/* Search bar */}
            <div className="absolute top-3 left-3 z-10">
              <div className="relative">
                <Search size={13} className="absolute left-2 top-1/2 -translate-y-1/2 text-text-faint" />
                <input
                  value={lrSearch}
                  onChange={(e) => setLrSearch(e.target.value)}
                  placeholder="Highlight entity…"
                  className="w-44 rounded bg-bg-secondary pl-7 pr-3 py-1 text-xs focus:outline-none border border-border-default"
                />
              </div>
            </div>

            {(lrLoading) && (
              <div className="absolute inset-0 flex items-center justify-center">
                <RefreshCw size={20} className="animate-spin text-text-muted" />
              </div>
            )}

            {!lrLoading && !lrGraphData && (
              <div className="absolute inset-0 flex flex-col items-center justify-center gap-3 text-text-muted">
                <Database size={40} className="opacity-30" />
                <p className="text-sm">LightRAG graph not available.</p>
                <button
                  onClick={() => void syncMutation.mutate()}
                  disabled={syncMutation.isPending}
                  className="flex items-center gap-1.5 rounded bg-accent-teal/10 px-3 py-1.5 text-xs text-accent-teal hover:bg-accent-teal/20 transition-colors disabled:opacity-50"
                >
                  <RefreshCw size={12} className={syncMutation.isPending ? 'animate-spin' : ''} />
                  Sync Vault
                </button>
              </div>
            )}

            {!lrLoading && lrGraphData && (
              <canvas
                ref={lrCanvasRef}
                width={800}
                height={600}
                className="w-full h-full"
                style={{ cursor: 'pointer' }}
              />
            )}
          </div>

          {/* Entity sidebar */}
          <div className="w-64 border-l border-border-default bg-bg-secondary flex flex-col flex-shrink-0">
            <div className="flex items-center justify-between gap-2 px-3 py-2 border-b border-border-default">
              <div className="flex items-center gap-1.5">
                <Layers size={13} className="text-text-muted" />
                <span className="text-xs font-medium">Entities</span>
                {!entitiesLoading && (
                  <span className="rounded-full bg-bg-tertiary px-1.5 py-0.5 text-xs text-text-faint">
                    {allEntities.length}
                  </span>
                )}
              </div>
            </div>

            <div className="px-3 py-2 border-b border-border-default">
              <div className="relative">
                <Search size={11} className="absolute left-2 top-1/2 -translate-y-1/2 text-text-faint" />
                <input
                  value={entitySearch}
                  onChange={(e) => setEntitySearch(e.target.value)}
                  placeholder="Filter entities…"
                  className="w-full rounded bg-bg-primary pl-6 pr-2 py-1 text-xs focus:outline-none border border-border-default"
                />
              </div>
            </div>

            <div className="flex-1 overflow-y-auto">
              {entitiesLoading && (
                <div className="flex items-center justify-center py-8">
                  <RefreshCw size={16} className="animate-spin text-text-muted" />
                </div>
              )}
              {!entitiesLoading && filteredEntities.length === 0 && (
                <div className="flex flex-col items-center justify-center py-8 text-text-faint text-xs">
                  <Info size={20} className="mb-2 opacity-50" />
                  No entities found
                </div>
              )}
              {filteredEntities.map((e) => (
                <button
                  key={e.id}
                  onClick={() => void handleLrNodeClick(e.id)}
                  className="w-full flex items-center gap-2 px-3 py-2 text-xs hover:bg-bg-elevated transition-colors text-left"
                >
                  <span
                    className="w-2 h-2 rounded-full flex-shrink-0"
                    style={{ backgroundColor: clusterColor(e.cluster) }}
                  />
                  <span className="truncate text-text-primary">
                    {e.id}
                  </span>
                </button>
              ))}
            </div>
          </div>

          {/* LightRAG node detail panel */}
          {lrSelectedEntity && (
            <LightRagNodePanel
              entity={lrSelectedEntity}
              relations={lrRelations}
              notes={[]}
              onClose={() => setLrSelectedEntity(null)}
              onNavigateToNote={(noteId) => navigate(`/notes/${noteId}`)}
            />
          )}
        </div>
      )}
    </div>
  );
}
