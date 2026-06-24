/**
 * GraphPage
 * =========
 * Two-tab knowledge graph visualisation:
 *   "Wikilinks"          — react-force-graph-2d graph of note→note links
 *   "LightRAG Knowledge" — D3 force graph of LightRAG entities + relations
 *                          with a right-side entities sidebar panel
 *
 * Slice 16 additions
 * ------------------
 * - Entities sidebar panel on the LightRAG tab:
 *     • Fetches GET /api/v1/graph/entities (flat list, no links)
 *     • Search filter input (client-side)
 *     • Cluster colour dot per entity
 *     • Click row → opens existing LightRagNodePanel
 *     • Entity count badge in panel header
 * - Improved empty state: "Sync Vault" button triggers vault sync + spinner
 */

import React, { useCallback, useEffect, useRef, useState } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { useNavigate } from 'react-router-dom';
import { apiClient } from '@/api/client';
import {
  Search, RefreshCw, ZoomIn, ZoomOut, Maximize2, Filter, X, ChevronDown, ChevronRight, List,
} from 'lucide-react';
import type { ForceGraphMethods } from 'react-force-graph-2d';
import { LightRagNodePanel } from '../components/graph/LightRagNodePanel';
import type { LightRagEntity, LightRagRelation } from '../components/graph/LightRagNodePanel';
import api from '../services/api';
import type { GraphEntitySummary } from '../services/api';

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

interface WikilinkNode {
  id: string;
  title: string;
  note_type: string;
  status: string;
  folder: string;
  word_count: number;
  tag_count: number;
  incoming_link_count: number;
  outgoing_link_count: number;
  val?: number;
  color?: string;
  x?: number;
  y?: number;
}

interface WikilinkLink {
  source: string | WikilinkNode;
  target: string | WikilinkNode;
  link_text?: string;
}

interface LightRagNode {
  id: string;
  label: string;
  cluster?: number;
  x?: number;
  y?: number;
  vx?: number;
  vy?: number;
  fx?: number;
  fy?: number;
}

interface LightRagLink {
  source: string | LightRagNode;
  target: string | LightRagNode;
}

interface LightRagGraph {
  nodes: LightRagNode[];
  links: LightRagLink[];
}

const ForceGraph2D = React.lazy(() => import('react-force-graph-2d'));

// ---------------------------------------------------------------------------
// Colour helpers
// ---------------------------------------------------------------------------

const NOTE_TYPE_COLOURS: Record<string, string> = {
  permanent:  '#4f98a3',
  fleeting:   '#bb653b',
  literature: '#6daa45',
  journal:    '#a86fdf',
  map:        '#e8af34',
  reference:  '#5591c7',
  project:    '#dd6974',
  template:   '#797876',
};

const CLUSTER_COLOURS = [
  '#4f98a3','#bb653b','#6daa45','#a86fdf','#e8af34',
  '#5591c7','#dd6974','#797876','#fdab43','#d163a7',
];

function clusterColour(cluster?: number) {
  if (cluster === undefined) return '#797876';
  return CLUSTER_COLOURS[cluster % CLUSTER_COLOURS.length];
}

// ---------------------------------------------------------------------------
// Component
// ---------------------------------------------------------------------------

export default function GraphPage() {
  const navigate    = useNavigate();
  const queryClient = useQueryClient();
  const [tab, setTab]           = useState<'wikilinks' | 'lightrag'>('wikilinks');
  const [search, setSearch]     = useState('');
  const [filterOpen, setFilterOpen] = useState(false);
  const [typeFilter, setTypeFilter] = useState<string[]>([]);
  const [selectedNode, setSelectedNode] = useState<WikilinkNode | null>(null);

  // LightRAG tab state
  const [lrSearch, setLrSearch]         = useState('');
  const [lrNodes, setLrNodes]           = useState<LightRagNode[]>([]);
  const [lrLinks, setLrLinks]           = useState<LightRagLink[]>([]);
  const [lrSelectedEntity, setLrSelectedEntity] = useState<LightRagEntity | null>(null);
  const [lrSelectedRelations, setLrSelectedRelations] = useState<LightRagRelation[]>([]);
  const [entitiesPanelOpen, setEntitiesPanelOpen] = useState(true);
  const [entitySearch, setEntitySearch] = useState('');

  const fgRef    = useRef<ForceGraphMethods | null>(null);
  const canvasRef = useRef<HTMLCanvasElement | null>(null);
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  const lrSimRef    = useRef<any>(null);
  const lrCanvasRef = useRef<HTMLCanvasElement | null>(null);
  const animFrameRef = useRef<number | null>(null);

  // ── Data fetching ─────────────────────────────────────────────────────────

  const { data: graphData, isLoading: graphLoading } = useQuery({
    queryKey: ['graph-data'],
    queryFn: () => apiClient.get<{ nodes: WikilinkNode[]; links: WikilinkLink[] }>('/api/v1/graph/data').then(r => r.data),
    staleTime: 60_000,
  });

  const { data: lrData, isLoading: lrLoading } = useQuery({
    queryKey: ['lightrag-graph'],
    queryFn: () => apiClient.get<LightRagGraph>('/api/v1/graph/lightrag').then(r => r.data),
    staleTime: 60_000,
    enabled: tab === 'lightrag',
  });

  const { data: entitiesData } = useQuery({
    queryKey: ['graph-entities'],
    queryFn:  () => api.listGraphEntities(),
    staleTime: 60_000,
    enabled: tab === 'lightrag',
  });

  const syncMutation = useMutation({
    mutationFn: () => apiClient.post('/api/v1/graph/sync').then(r => r.data),
    onSuccess:  () => {
      queryClient.invalidateQueries({ queryKey: ['graph-data'] });
      queryClient.invalidateQueries({ queryKey: ['lightrag-graph'] });
      queryClient.invalidateQueries({ queryKey: ['graph-entities'] });
    },
  });

  // ── D3 canvas simulation for LightRAG ─────────────────────────────────────

  useEffect(() => {
    if (tab !== 'lightrag' || !lrData || !lrCanvasRef.current) return;

    import('d3-force').then((d3) => {
      if (!lrCanvasRef.current) return;
      const canvas  = lrCanvasRef.current;
      const ctx     = canvas.getContext('2d');
      if (!ctx) return;

      const nodes: LightRagNode[] = lrData.nodes.map((n) => ({ ...n }));
      const links: LightRagLink[] = lrData.links.map((l) => ({ ...l }));

      lrSimRef.current?.stop();
      if (animFrameRef.current) cancelAnimationFrame(animFrameRef.current);

      const sim = d3.forceSimulation<LightRagNode>(nodes)
        .force('link', d3.forceLink<LightRagNode, LightRagLink>(links).id((d) => d.id).distance(80))
        .force('charge', d3.forceManyBody().strength(-120))
        .force('center', d3.forceCenter(canvas.width / 2, canvas.height / 2))
        .force('collision', d3.forceCollide(18));

      lrSimRef.current = sim;
      setLrNodes(nodes);
      setLrLinks(links);

      function draw() {
        if (!ctx || !canvas) return;
        ctx.clearRect(0, 0, canvas.width, canvas.height);

        // Draw links
        ctx.strokeStyle = 'oklch(0.5 0 0 / 0.3)';
        ctx.lineWidth = 1;
        for (const link of links) {
          const s = link.source as LightRagNode;
          const t = link.target as LightRagNode;
          if (s.x == null || s.y == null || t.x == null || t.y == null) continue;
          ctx.beginPath();
          ctx.moveTo(s.x, s.y);
          ctx.lineTo(t.x, t.y);
          ctx.stroke();
        }

        // Draw nodes
        for (const node of nodes) {
          if (node.x == null || node.y == null) continue;
          ctx.beginPath();
          ctx.arc(node.x, node.y, 6, 0, 2 * Math.PI);
          ctx.fillStyle = clusterColour(node.cluster);
          ctx.fill();
        }
      }

      sim.on('tick', () => {
        animFrameRef.current = requestAnimationFrame(draw);
      });

      sim.on('end', draw);
    });

    return () => {
      lrSimRef.current?.stop();
      if (animFrameRef.current) cancelAnimationFrame(animFrameRef.current);
    };
  }, [tab, lrData]);

  // ── Wikilink graph helpers ─────────────────────────────────────────────────

  const filteredNodes = (graphData?.nodes ?? []).filter((n) => {
    const matchSearch = !search || n.title.toLowerCase().includes(search.toLowerCase());
    const matchType   = typeFilter.length === 0 || typeFilter.includes(n.note_type);
    return matchSearch && matchType;
  });

  const filteredNodeIds = new Set(filteredNodes.map((n) => n.id));
  const filteredLinks   = (graphData?.links ?? []).filter((l) => {
    const src = typeof l.source === 'string' ? l.source : (l.source as WikilinkNode).id;
    const tgt = typeof l.target === 'string' ? l.target : (l.target as WikilinkNode).id;
    return filteredNodeIds.has(src) && filteredNodeIds.has(tgt);
  });

  const graphDataFiltered = { nodes: filteredNodes, links: filteredLinks };

  const handleNodeClick = useCallback((node: WikilinkNode) => {
    setSelectedNode(node);
  }, []);

  const handleZoomIn  = () => fgRef.current?.zoom(1.5, 300);
  const handleZoomOut = () => fgRef.current?.zoom(0.75, 300);
  const handleFit     = () => fgRef.current?.zoomToFit(400, 40);

  // LightRAG entity click → fetch full entity + relations
  const handleLrNodeClick = useCallback(async (nodeId: string) => {
    try {
      const [entityRes, relationsRes] = await Promise.all([
        apiClient.get<LightRagEntity>(`/api/v1/graph/entities/${encodeURIComponent(nodeId)}`),
        apiClient.get<{ relations: LightRagRelation[] }>(`/api/v1/graph/entities/${encodeURIComponent(nodeId)}/relations`),
      ]);
      setLrSelectedEntity(entityRes.data);
      setLrSelectedRelations(relationsRes.data.relations ?? []);
    } catch {
      // ignore — node panel stays closed
    }
  }, []);

  const handleCanvasClick = useCallback((e: React.MouseEvent<HTMLCanvasElement>) => {
    if (!lrCanvasRef.current) return;
    const rect = lrCanvasRef.current.getBoundingClientRect();
    const mx = e.clientX - rect.left;
    const my = e.clientY - rect.top;
    const HIT_R = 10;
    for (const node of lrNodes) {
      if (node.x == null || node.y == null) continue;
      const dx = node.x - mx;
      const dy = node.y - my;
      if (dx * dx + dy * dy < HIT_R * HIT_R) {
        void handleLrNodeClick(node.id);
        break;
      }
    }
  }, [lrNodes, handleLrNodeClick]);

  // ── Sidebar entity list (LightRAG tab) ────────────────────────────────────

  const allEntities: GraphEntitySummary[] = entitiesData ?? [];
  const filteredEntities = allEntities.filter(
    (e) => !entitySearch || e.entity_id.toLowerCase().includes(entitySearch.toLowerCase())
  );

  // ── Stats ─────────────────────────────────────────────────────────────────

  const nodeCount = graphData?.nodes.length ?? 0;
  const linkCount = graphData?.links.length ?? 0;
  const orphanCount = graphData?.nodes.filter(
    (n) => n.incoming_link_count === 0 && n.outgoing_link_count === 0
  ).length ?? 0;

  // ── Render ────────────────────────────────────────────────────────────────

  const NOTE_TYPES = ['permanent','fleeting','literature','journal','map','reference','project','template'];

  return (
    <div className="flex h-full flex-col bg-bg-primary text-text-primary">

      {/* ── Header ──────────────────────────────────────────────────────── */}
      <div className="flex items-center justify-between gap-3 border-b border-border px-4 py-2 flex-shrink-0">
        <div className="flex items-center gap-2">
          <h1 className="text-sm font-semibold">Knowledge Graph</h1>
          <div className="flex rounded border border-border overflow-hidden">
            {(['wikilinks','lightrag'] as const).map((t) => (
              <button
                key={t}
                onClick={() => setTab(t)}
                className={`px-3 py-1 text-xs font-medium transition-colors ${
                  tab === t
                    ? 'bg-accent-teal/20 text-accent-teal'
                    : 'text-text-muted hover:text-text-primary hover:bg-bg-tertiary'
                }`}
              >
                {t === 'wikilinks' ? 'Wikilinks' : 'LightRAG'}
              </button>
            ))}
          </div>
        </div>

        <div className="flex items-center gap-2">
          {/* Stats */}
          {tab === 'wikilinks' && (
            <div className="flex items-center gap-3 text-xs text-text-muted">
              <span>{nodeCount} notes</span>
              <span>{linkCount} links</span>
              {orphanCount > 0 && <span className="text-accent-orange">{orphanCount} orphans</span>}
            </div>
          )}

          {/* Search */}
          <div className="relative">
            <Search size={12} className="absolute left-2 top-1/2 -translate-y-1/2 text-text-faint" />
            <input
              value={tab === 'wikilinks' ? search : lrSearch}
              onChange={(e) => tab === 'wikilinks' ? setSearch(e.target.value) : setLrSearch(e.target.value)}
              placeholder="Search nodes…"
              className="w-44 rounded border border-border bg-bg-secondary pl-7 pr-2 py-1 text-xs text-text-primary placeholder:text-text-faint focus:outline-none focus:border-accent-teal"
            />
          </div>

          {/* Filter toggle (wikilinks only) */}
          {tab === 'wikilinks' && (
            <button
              onClick={() => setFilterOpen(!filterOpen)}
              className={`rounded p-1.5 text-xs transition-colors ${
                filterOpen || typeFilter.length > 0
                  ? 'bg-accent-teal/20 text-accent-teal'
                  : 'text-text-muted hover:bg-bg-tertiary'
              }`}
              title="Filter by type"
            >
              <Filter size={13} />
            </button>
          )}

          {/* Sync */}
          <button
            onClick={() => syncMutation.mutate()}
            disabled={syncMutation.isPending}
            className="flex items-center gap-1 rounded bg-bg-tertiary px-2.5 py-1 text-xs text-text-muted hover:text-text-primary transition-colors disabled:opacity-50"
          >
            <RefreshCw size={11} className={syncMutation.isPending ? 'animate-spin' : ''} />
            {syncMutation.isPending ? 'Syncing…' : 'Sync'}
          </button>
        </div>
      </div>

      {/* ── Type filter dropdown ─────────────────────────────────────────── */}
      {filterOpen && tab === 'wikilinks' && (
        <div className="flex flex-wrap gap-1.5 border-b border-border px-4 py-2 flex-shrink-0">
          {NOTE_TYPES.map((type) => (
            <button
              key={type}
              onClick={() =>
                setTypeFilter((prev) =>
                  prev.includes(type) ? prev.filter((t) => t !== type) : [...prev, type]
                )
              }
              className={`rounded-full px-2.5 py-0.5 text-xs font-medium transition-colors border ${
                typeFilter.includes(type)
                  ? 'border-transparent text-bg-primary'
                  : 'border-border text-text-muted hover:border-text-muted'
              }`}
              style={typeFilter.includes(type) ? { background: NOTE_TYPE_COLOURS[type] } : {}}
            >
              {type}
            </button>
          ))}
          {typeFilter.length > 0 && (
            <button
              onClick={() => setTypeFilter([])}
              className="flex items-center gap-0.5 rounded-full border border-border px-2 py-0.5 text-xs text-text-muted hover:text-text-primary"
            >
              <X size={10} /> Clear
            </button>
          )}
        </div>
      )}

      {/* ── Main area ───────────────────────────────────────────────────── */}
      <div className="flex flex-1 min-h-0 overflow-hidden">

        {/* ── Wikilinks tab ─────────────────────────────────────────────── */}
        {tab === 'wikilinks' && (
          <div className="relative flex-1 min-w-0">
            {graphLoading ? (
              <div className="flex h-full items-center justify-center text-text-muted text-sm">
                Loading graph…
              </div>
            ) : nodeCount === 0 ? (
              <div className="flex h-full flex-col items-center justify-center gap-3 text-text-muted">
                <p className="text-sm">No notes with wikilinks yet.</p>
                <button
                  onClick={() => syncMutation.mutate()}
                  disabled={syncMutation.isPending}
                  className="flex items-center gap-1 rounded bg-accent-teal/20 px-3 py-1.5 text-xs text-accent-teal hover:bg-accent-teal/30 transition-colors disabled:opacity-50"
                >
                  <RefreshCw size={12} className={syncMutation.isPending ? 'animate-spin' : ''} />
                  Sync Vault
                </button>
              </div>
            ) : (
              <React.Suspense fallback={<div className="flex h-full items-center justify-center text-text-muted text-sm">Loading renderer…</div>}>
                <ForceGraph2D
                  ref={fgRef}
                  graphData={graphDataFiltered as { nodes: WikilinkNode[]; links: WikilinkLink[] }}
                  nodeId="id"
                  nodeLabel="title"
                  nodeColor={(n) => NOTE_TYPE_COLOURS[(n as WikilinkNode).note_type] ?? '#797876'}
                  nodeVal={(n) => Math.max(1, ((n as WikilinkNode).incoming_link_count ?? 0) + 1)}
                  linkColor={() => 'oklch(0.5 0 0 / 0.3)'}
                  linkWidth={1}
                  backgroundColor="transparent"
                  onNodeClick={(n) => handleNodeClick(n as WikilinkNode)}
                  onNodeRightClick={(n) => navigate(`/notes/${(n as WikilinkNode).id}`)}
                  width={undefined}
                  height={undefined}
                />
              </React.Suspense>
            )}

            {/* Zoom controls */}
            <div className="absolute bottom-4 right-4 flex flex-col gap-1">
              <button onClick={handleZoomIn}  className="rounded bg-bg-secondary border border-border p-1.5 text-text-muted hover:text-text-primary"><ZoomIn  size={13} /></button>
              <button onClick={handleZoomOut} className="rounded bg-bg-secondary border border-border p-1.5 text-text-muted hover:text-text-primary"><ZoomOut size={13} /></button>
              <button onClick={handleFit}     className="rounded bg-bg-secondary border border-border p-1.5 text-text-muted hover:text-text-primary"><Maximize2 size={13} /></button>
            </div>

            {/* Selected node panel */}
            {selectedNode && (
              <div className="absolute top-3 left-3 w-64 rounded-lg border border-border bg-bg-secondary p-3 shadow-lg text-xs">
                <div className="flex items-start justify-between gap-2 mb-2">
                  <span className="font-semibold text-text-primary truncate">{selectedNode.title}</span>
                  <button onClick={() => setSelectedNode(null)} className="text-text-faint hover:text-text-primary"><X size={12} /></button>
                </div>
                <div className="space-y-0.5 text-text-muted">
                  <div>Type: <span className="text-text-primary">{selectedNode.note_type}</span></div>
                  <div>Folder: <span className="text-text-primary">{selectedNode.folder}</span></div>
                  <div>In: <span className="text-text-primary">{selectedNode.incoming_link_count}</span> / Out: <span className="text-text-primary">{selectedNode.outgoing_link_count}</span></div>
                </div>
                <button
                  onClick={() => navigate(`/notes/${selectedNode.id}`)}
                  className="mt-2 w-full rounded bg-accent-teal/20 py-1 text-accent-teal hover:bg-accent-teal/30 transition-colors"
                >
                  Open note
                </button>
              </div>
            )}
          </div>
        )}

        {/* ── LightRAG tab ──────────────────────────────────────────────── */}
        {tab === 'lightrag' && (
          <div className="flex flex-1 min-w-0">

            {/* Canvas */}
            <div className="relative flex-1 min-w-0">
              {lrLoading ? (
                <div className="flex h-full items-center justify-center text-text-muted text-sm">Loading graph…</div>
              ) : !lrData || lrData.nodes.length === 0 ? (
                <div className="flex h-full flex-col items-center justify-center gap-3 text-text-muted">
                  <p className="text-sm">No LightRAG graph data yet.</p>
                  <button
                    onClick={() => syncMutation.mutate()}
                    disabled={syncMutation.isPending}
                    className="flex items-center gap-1 rounded bg-accent-teal/20 px-3 py-1.5 text-xs text-accent-teal hover:bg-accent-teal/30 transition-colors disabled:opacity-50"
                  >
                    <RefreshCw size={12} className={syncMutation.isPending ? 'animate-spin' : ''} />
                    Sync Vault
                  </button>
                </div>
              ) : (
                <canvas
                  ref={lrCanvasRef}
                  onClick={handleCanvasClick}
                  className="w-full h-full cursor-crosshair"
                  style={{ display: 'block' }}
                />
              )}

              {lrSelectedEntity && (
                <LightRagNodePanel
                  entity={lrSelectedEntity}
                  relations={lrSelectedRelations}
                  onRelationClick={(rel) => {
                    const otherId = rel.source === lrSelectedEntity.entity_id ? rel.target : rel.source;
                    void handleLrNodeClick(otherId);
                  }}
                  onClose={() => { setLrSelectedEntity(null); setLrSelectedRelations([]); }}
                />
              )}
            </div>

            {/* Entities sidebar */}
            <div className={`flex-shrink-0 border-l border-border bg-bg-secondary transition-all ${
              entitiesPanelOpen ? 'w-56' : 'w-8'
            }`}>
              <div className="flex items-center justify-between px-2 py-1.5 border-b border-border">
                {entitiesPanelOpen && (
                  <span className="text-xs font-medium text-text-muted">
                    Entities
                    {allEntities.length > 0 && (
                      <span className="ml-1 rounded-full bg-bg-tertiary px-1.5 py-0.5 text-xs">{allEntities.length}</span>
                    )}
                  </span>
                )}
                <button
                  onClick={() => setEntitiesPanelOpen(!entitiesPanelOpen)}
                  className="ml-auto rounded p-0.5 text-text-faint hover:text-text-primary"
                  title={entitiesPanelOpen ? 'Collapse' : 'Expand entities'}
                >
                  {entitiesPanelOpen ? <ChevronRight size={13} /> : <List size={13} />}
                </button>
              </div>

              {entitiesPanelOpen && (
                <>
                  <div className="px-2 py-1.5 border-b border-border">
                    <div className="relative">
                      <Search size={11} className="absolute left-1.5 top-1/2 -translate-y-1/2 text-text-faint" />
                      <input
                        value={entitySearch}
                        onChange={(e) => setEntitySearch(e.target.value)}
                        placeholder="Filter…"
                        className="w-full rounded border border-border bg-bg-tertiary pl-5 pr-2 py-0.5 text-xs placeholder:text-text-faint focus:outline-none focus:border-accent-teal"
                      />
                    </div>
                  </div>
                  <div className="overflow-y-auto flex-1" style={{ maxHeight: 'calc(100% - 72px)' }}>
                    {filteredEntities.length === 0 ? (
                      <p className="px-3 py-4 text-xs text-text-faint text-center">No entities</p>
                    ) : (
                      filteredEntities.map((e) => (
                        <button
                          key={e.entity_id}
                          onClick={() => void handleLrNodeClick(e.entity_id)}
                          className="flex w-full items-center gap-2 px-2 py-1 text-left hover:bg-bg-tertiary transition-colors group"
                        >
                          <span
                            className="h-2 w-2 flex-shrink-0 rounded-full"
                            style={{ background: clusterColour(e.cluster) }}
                          />
                          <span className="truncate text-xs text-text-secondary group-hover:text-text-primary">
                            {e.entity_id}
                          </span>
                        </button>
                      ))
                    )}
                  </div>
                </>
              )}
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
