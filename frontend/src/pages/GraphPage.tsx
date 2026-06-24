/**
 * GraphPage.tsx
 * Tab-based knowledge-graph page using TanStack Query.
 *
 * Tab 1 — Wikilinks:          GraphView2D + GraphControls + NodeDetailOverlay
 * Tab 2 — LightRAG Knowledge: entity list + lightrag graph health check
 *
 * The toolbar always shows:
 *   • "Filter nodes…" input → drives highlightQuery (wikilinks graph)
 *   • Refresh / Sync Vault buttons
 *
 * The LightRAG panel additionally shows its own entity-filter input.
 */

import React, { useRef, useCallback, useState, lazy, Suspense } from 'react';
import { useQuery, useQueryClient } from '@tanstack/react-query';
import type { ForceGraphMethods } from 'react-force-graph-2d';
import type { GraphData, GraphNode } from '../types';
import api from '../services/api';
import type { GraphEntitySummary } from '../services/api';
import { GraphView2D, type ForceNode } from '../components/graph/GraphView2D';
import { GraphControls } from '../components/graph/GraphControls';
import { NodeDetailOverlay } from '../components/graph/NodeDetailOverlay';
import { useGraphStore } from '../store/graphStore';
import { toForceGraphData, nodeColor, nodeVal, clusterColor } from '../lib/graphUtils';
import './GraphPage.css';

type Tab = 'wikilinks' | 'lightrag';

interface LightRagData {
  entities: GraphEntitySummary[];
  relations?: unknown[];
}

export default function GraphPage() {
  const queryClient = useQueryClient();
  const graphRef    = useRef<ForceGraphMethods>(null);

  const [activeTab,    setActiveTab]    = useState<Tab>('wikilinks');
  const [entityFilter, setEntityFilter] = useState('');
  const [syncing,      setSyncing]      = useState(false);
  const [nodeFilter,   setNodeFilter]   = useState('');

  // Graph view state from Zustand store
  const {
    selectedNodeId, selectNode,
    clusterMode, neighborhoodMode,
    highlightQuery, setHighlightQuery,
    showLabels,
  } = useGraphStore();

  // ── Wikilinks graph ────────────────────────────────────────────
  const {
    data: graphData,
    isLoading: graphLoading,
    isError: graphIsError,
    error: graphError,
  } = useQuery<GraphData>({
    queryKey: ['graph'],
    queryFn:  () => api.getFullGraph() as Promise<GraphData>,
    retry: false,
  });

  // ── LightRAG graph health ───────────────────────────────────
  const { isLoading: lrGraphLoading, isError: lrGraphIsError, error: lrGraphError } = useQuery({
    queryKey: ['lightrag-graph'],
    queryFn:  () => api.getLightRagGraph(),
    enabled:  activeTab === 'lightrag',
    retry: false,
  });

  const { data: lrData, isLoading: lrEntitiesLoading, isError: lrEntitiesIsError, error: lrEntitiesError } =
    useQuery<LightRagData>({
      queryKey: ['graph-entities'],
      queryFn:  () => api.getGraphEntities() as Promise<LightRagData>,
      enabled:  activeTab === 'lightrag',
      retry: false,
    });

  const lrLoading = lrGraphLoading || lrEntitiesLoading;
  const lrIsError = lrGraphIsError || lrEntitiesIsError;
  const lrError   = lrGraphError   ?? lrEntitiesError;

  // ── Derived graph data ─────────────────────────────────────────────
  const allNodes  = graphData?.nodes ?? [];
  const edgeCount = graphData?.edges?.length ?? 0;

  // Build force-graph data from the new graphUtils helper
  const forceData = graphData ? toForceGraphData(graphData) : { nodes: [], links: [] };

  // Apply node filter (from the toolbar input) and store highlight query
  const filterQuery = nodeFilter.trim().toLowerCase();
  const filteredNodes = React.useMemo(() => {
    if (!filterQuery) return forceData.nodes as ForceNode[];
    return (forceData.nodes as ForceNode[]).filter(
      (n) => n.title?.toLowerCase().includes(filterQuery),
    );
  }, [forceData, filterQuery]);

  // Sync nodeFilter into graphStore.highlightQuery so GraphView2D dims non-matching nodes
  React.useEffect(() => {
    if (typeof setHighlightQuery === 'function') {
      setHighlightQuery(nodeFilter);
    }
  }, [nodeFilter, setHighlightQuery]);

  const highlightIds = React.useMemo(() => {
    const q = (highlightQuery ?? nodeFilter).trim().toLowerCase();
    if (!q) return new Set<string>();
    return new Set(
      (forceData.nodes as ForceNode[])
        .filter((n) => n.title?.toLowerCase().includes(q))
        .map((n) => n.id),
    );
  }, [forceData, highlightQuery, nodeFilter]);

  const nodeCount = filteredNodes.length;

  // Build filtered links (both endpoints must be in the filtered set)
  const filteredLinks = React.useMemo(() => {
    if (!filterQuery) return forceData.links;
    const ids = new Set(filteredNodes.map((n) => n.id));
    return forceData.links.filter(
      (l) => ids.has((l as { source: string }).source) && ids.has((l as { target: string }).target),
    );
  }, [forceData, filteredNodes, filterQuery]);

  // Resolve the selected GraphNode for the overlay
  const selectedNode = React.useMemo(
    () => selectedNodeId
      ? (allNodes.find((n) => (n.note_id ?? n.id) === selectedNodeId) ?? null)
      : null,
    [allNodes, selectedNodeId],
  ) as GraphNode | null;

  // LightRAG entities
  const allEntities = lrData?.entities ?? [];
  const filteredEntities = entityFilter.trim()
    ? allEntities.filter((e) =>
        e.id?.toLowerCase().includes(entityFilter.toLowerCase()) ||
        e.label?.toLowerCase().includes(entityFilter.toLowerCase()),
      )
    : allEntities;

  // ── Handlers ─────────────────────────────────────────────────
  const handleRefresh = useCallback(() => {
    queryClient.invalidateQueries({ queryKey: ['graph'] });
    if (activeTab === 'lightrag') {
      queryClient.invalidateQueries({ queryKey: ['lightrag-graph'] });
      queryClient.invalidateQueries({ queryKey: ['graph-entities'] });
    }
  }, [queryClient, activeTab]);

  const handleSyncVault = useCallback(async () => {
    setSyncing(true);
    try {
      await api.triggerVaultSync();
      queryClient.invalidateQueries({ queryKey: ['graph'] });
    } catch (_e) {
      // non-fatal
    } finally {
      setSyncing(false);
    }
  }, [queryClient]);

  const handleNodeClick = useCallback((node: ForceNode) => {
    selectNode(node.id);
    graphRef.current?.centerAt(node.x ?? 0, node.y ?? 0, 600);
    graphRef.current?.zoom(2.5, 600);
  }, [selectNode]);

  // Read the current zoom level first (with its own fallback), THEN do the
  // arithmetic. This ensures ?? has a null/undefined to guard against and
  // avoids the esbuild "?? always returns left operand" warning that fires
  // when the fallback is placed after a multiply/divide result (which is
  // always a number — never null/undefined — even when .zoom?.() is undefined).
  const getZoom = () =>
    (graphRef.current as unknown as { zoom?: () => number } | null)?.zoom?.() ?? 1;

  const handleZoomIn  = () => graphRef.current?.zoom(getZoom() * 1.3, 200);
  const handleZoomOut = () => graphRef.current?.zoom(getZoom() / 1.3, 200);
  const handleZoomFit = () => graphRef.current?.zoomToFit(400, 40);

  // ── Render ─────────────────────────────────────────────────────────
  return (
    <div className="graph-page">
      {/* Header */}
      <div className="graph-page__header">
        <h1 className="graph-page__title">Knowledge Graph</h1>

        <div className="graph-page__tabs">
          <button
            aria-selected={activeTab === 'wikilinks'}
            className={`graph-page__tab${activeTab === 'wikilinks' ? ' graph-page__tab--active' : ''}`}
            onClick={() => setActiveTab('wikilinks')}
          >
            Wikilinks
          </button>
          <button
            aria-selected={activeTab === 'lightrag'}
            className={`graph-page__tab${activeTab === 'lightrag' ? ' graph-page__tab--active' : ''}`}
            onClick={() => setActiveTab('lightrag')}
          >
            LightRAG Knowledge
          </button>
        </div>

        {/* Toolbar — always visible */}
        <div className="graph-page__toolbar" role="toolbar" aria-label="Graph controls">
          {/* Node filter — always shown; test queries getAllByPlaceholderText(/filter nodes/i)[0] */}
          <input
            className="graph-page__search"
            type="search"
            placeholder="Filter nodes…"
            value={nodeFilter}
            onChange={(e) => setNodeFilter(e.target.value)}
            aria-label="Filter nodes"
          />
          <button className="graph-page__refresh-btn" onClick={handleRefresh} aria-label="Refresh">
            Refresh
          </button>
        </div>
      </div>

      {/* ── Wikilinks tab ── */}
      {activeTab === 'wikilinks' && (
        <div className="graph-page__wikilinks relative">
          {graphLoading && (
            <div className="graph-page__loading">
              <span className="graph-page__spinner" aria-label="Loading graph" />
            </div>
          )}
          {graphIsError && (
            <div className="graph-page__error" role="alert">
              <p>Failed to load graph: {String(graphError)}</p>
              <button onClick={handleRefresh}>Retry</button>
            </div>
          )}
          {!graphLoading && !graphIsError && allNodes.length === 0 && (
            <div className="graph-page__empty">
              <p>No notes in the graph yet.</p>
              <button
                className="graph-page__sync-btn"
                onClick={handleSyncVault}
                disabled={syncing}
                aria-label="Sync Vault"
              >
                {syncing ? 'Syncing…' : 'Sync Vault'}
              </button>
            </div>
          )}
          {!graphLoading && !graphIsError && allNodes.length > 0 && (
            <>
              <div className="graph-page__stats">
                <span className="graph-page__node-badge">{nodeCount} nodes</span>
                <span className="graph-page__edge-badge">{edgeCount} edges</span>
              </div>

              {/* Floating controls overlay */}
              <GraphControls
                onZoomIn={handleZoomIn}
                onZoomOut={handleZoomOut}
                onZoomToFit={handleZoomFit}
                onCenterGraph={() => graphRef.current?.zoomToFit(400, 40)}
              />

              {/* Graph canvas — receives only filtered nodes so stub shows correct count */}
              <Suspense fallback={<div className="graph-page__canvas-loading">Loading graph…</div>}>
                <GraphView2D
                  ref={graphRef}
                  nodes={filteredNodes}
                  links={filteredLinks as import('../components/graph/GraphView2D').ForceLink[]}
                  highlightIds={highlightIds}
                  clusterMode={clusterMode}
                  showLabels={showLabels}
                  onNodeClick={handleNodeClick}
                />
              </Suspense>

              {/* Node detail overlay */}
              <NodeDetailOverlay
                node={selectedNode}
                onClose={() => selectNode(null)}
              />
            </>
          )}
        </div>
      )}

      {/* ── LightRAG Knowledge tab ── */}
      {activeTab === 'lightrag' && (
        <div className="graph-page__lightrag">
          {/* Entity filter (LightRAG tab only) */}
          <div className="graph-page__lr-toolbar">
            <input
              className="graph-page__search"
              type="search"
              placeholder="Filter entities…"
              value={entityFilter}
              onChange={(e) => setEntityFilter(e.target.value)}
              aria-label="Filter entities"
            />
          </div>
          {lrLoading && (
            <div role="status" className="graph-page__lr-loading">Loading entities…</div>
          )}
          {!lrLoading && lrIsError && (
            <div role="alert" className="graph-page__lr-error">
              LightRAG graph not available: {String(lrError)}
            </div>
          )}
          {!lrLoading && !lrIsError && (
            <>
              <p className="graph-page__lr-count">{filteredEntities.length} entities</p>
              <ul className="graph-page__entity-list" aria-label="Entity list">
                {filteredEntities.map((entity) => (
                  <li key={entity.id} className="graph-page__entity-item">
                    <span className="graph-page__entity-id">{entity.id}</span>
                    {entity.label && entity.label !== entity.id && (
                      <span className="graph-page__entity-label">{entity.label}</span>
                    )}
                  </li>
                ))}
              </ul>
              {filteredEntities.length === 0 && !entityFilter && (
                <p className="graph-page__lr-empty">No LightRAG entities indexed yet.</p>
              )}
            </>
          )}
        </div>
      )}
    </div>
  );
}
