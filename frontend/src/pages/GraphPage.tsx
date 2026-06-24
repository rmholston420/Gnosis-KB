/**
 * GraphPage.tsx
 * =============
 * Tab-based knowledge-graph page.
 *
 * Tab 1 — Wikilinks:       react-force-graph-2d visualisation of vault link graph
 * Tab 2 — LightRAG Knowledge: flat entity list from the LightRAG knowledge graph
 *
 * API calls:
 *   api.getFullGraph()      → { nodes, edges }   (wikilinks graph)
 *   api.getGraphEntities()  → { entities }        (LightRAG entity list)
 */

import React, { useEffect, useState, useCallback, lazy, Suspense } from 'react';
import type { GraphData, GraphNode } from '../types';
import api from '../services/api';
import type { GraphEntitySummary } from '../services/api';
import './GraphPage.css';

// Lazy-load ForceGraph so jsdom / SSR never touches the WebGL canvas.
const ForceGraph2D = lazy(() => import('react-force-graph-2d'));

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------
type Tab = 'wikilinks' | 'lightrag';

interface LightRagData {
  entities: GraphEntitySummary[];
  relations?: unknown[];
}

// ---------------------------------------------------------------------------
// Component
// ---------------------------------------------------------------------------
export default function GraphPage() {
  // ── Wikilinks graph ──────────────────────────────────────────────────────
  const [graphData,    setGraphData]    = useState<GraphData | null>(null);
  const [graphLoading, setGraphLoading] = useState(true);
  const [graphError,   setGraphError]   = useState<string | null>(null);

  // ── LightRAG entities ────────────────────────────────────────────────────
  const [lrData,    setLrData]    = useState<LightRagData | null>(null);
  const [lrLoading, setLrLoading] = useState(false);
  const [lrError,   setLrError]   = useState<string | null>(null);

  // ── UI state ─────────────────────────────────────────────────────────────
  const [activeTab,     setActiveTab]     = useState<Tab>('wikilinks');
  const [nodeFilter,    setNodeFilter]    = useState('');
  const [entityFilter,  setEntityFilter]  = useState('');
  const [selectedNode,  setSelectedNode]  = useState<GraphNode | null>(null);
  const [syncing,       setSyncing]       = useState(false);

  // ── Fetch wikilinks graph on mount ───────────────────────────────────────
  useEffect(() => {
    setGraphLoading(true);
    api.getFullGraph()
      .then((d: unknown) => {
        setGraphData(d as GraphData);
        setGraphLoading(false);
      })
      .catch((e: unknown) => {
        setGraphError(String(e));
        setGraphLoading(false);
      });
  }, []);

  // ── Fetch LightRAG entities when tab switches ────────────────────────────
  useEffect(() => {
    if (activeTab !== 'lightrag') return;
    setLrLoading(true);
    setLrError(null);
    api.getGraphEntities()
      .then((d: unknown) => {
        setLrData(d as LightRagData);
        setLrLoading(false);
      })
      .catch((e: unknown) => {
        setLrError(String(e));
        setLrLoading(false);
      });
  }, [activeTab]);

  // ── Refresh handler ──────────────────────────────────────────────────────
  const handleRefresh = useCallback(() => {
    setGraphLoading(true);
    setGraphError(null);
    api.getFullGraph()
      .then((d: unknown) => {
        setGraphData(d as GraphData);
        setGraphLoading(false);
      })
      .catch((e: unknown) => {
        setGraphError(String(e));
        setGraphLoading(false);
      });
    if (activeTab === 'lightrag') {
      setLrLoading(true);
      api.getGraphEntities()
        .then((d: unknown) => { setLrData(d as LightRagData); setLrLoading(false); })
        .catch((e: unknown) => { setLrError(String(e)); setLrLoading(false); });
    }
  }, [activeTab]);

  // ── Sync vault handler ───────────────────────────────────────────────────
  const handleSyncVault = useCallback(async () => {
    setSyncing(true);
    try {
      await api.triggerVaultSync();
      // Re-fetch after sync
      const d = await api.getFullGraph();
      setGraphData(d as GraphData);
    } catch (_e) {
      // non-fatal
    } finally {
      setSyncing(false);
    }
  }, []);

  // ── Derived ──────────────────────────────────────────────────────────────
  const allNodes   = graphData?.nodes ?? [];
  const nodeCount  = allNodes.length;
  const edgeCount  = graphData?.edges?.length ?? 0;

  const filteredNodes = nodeFilter.trim()
    ? allNodes.filter((n) =>
        n.title?.toLowerCase().includes(nodeFilter.toLowerCase())
      )
    : allNodes;

  const allEntities  = lrData?.entities ?? [];
  const filteredEntities = entityFilter.trim()
    ? allEntities.filter((e) =>
        e.label?.toLowerCase().includes(entityFilter.toLowerCase()) ||
        e.id?.toLowerCase().includes(entityFilter.toLowerCase())
      )
    : allEntities;

  const forceGraphData = {
    nodes: filteredNodes.map((n) => ({ id: n.id, name: n.title, type: n.note_type })),
    links: (graphData?.edges ?? []).map((e) => ({ source: e.source, target: e.target })),
  };

  // ── Loading state ─────────────────────────────────────────────────────────
  if (graphLoading) {
    return (
      <div className="graph-page graph-page--loading">
        <span className="graph-page__spinner" aria-label="Loading graph" />
      </div>
    );
  }

  // ── Error state ───────────────────────────────────────────────────────────
  if (graphError) {
    return (
      <div className="graph-page graph-page--error" role="alert">
        <p>Failed to load graph: {graphError}</p>
        <button onClick={handleRefresh}>Retry</button>
      </div>
    );
  }

  // ── Main render ───────────────────────────────────────────────────────────
  return (
    <div className="graph-page">
      {/* ── Page heading ── */}
      <div className="graph-page__header">
        <h1 className="graph-page__title">Knowledge Graph</h1>

        {/* ── Tab bar ── */}
        <div className="graph-page__tabs" role="tablist">
          <button
            role="tab"
            aria-selected={activeTab === 'wikilinks'}
            className={`graph-page__tab${activeTab === 'wikilinks' ? ' graph-page__tab--active' : ''}`}
            onClick={() => setActiveTab('wikilinks')}
          >
            Wikilinks
          </button>
          <button
            role="tab"
            aria-selected={activeTab === 'lightrag'}
            className={`graph-page__tab${activeTab === 'lightrag' ? ' graph-page__tab--active' : ''}`}
            onClick={() => setActiveTab('lightrag')}
          >
            LightRAG Knowledge
          </button>
        </div>

        {/* ── Toolbar ── */}
        <div className="graph-page__toolbar" role="toolbar" aria-label="Graph controls">
          {activeTab === 'wikilinks' && (
            <input
              className="graph-page__search"
              type="search"
              placeholder="Filter nodes\u2026"
              value={nodeFilter}
              onChange={(e) => setNodeFilter(e.target.value)}
              aria-label="Filter nodes"
            />
          )}
          {activeTab === 'lightrag' && (
            <input
              className="graph-page__search"
              type="search"
              placeholder="Filter entities\u2026"
              value={entityFilter}
              onChange={(e) => setEntityFilter(e.target.value)}
              aria-label="Filter entities"
            />
          )}
          <button
            className="graph-page__refresh-btn"
            onClick={handleRefresh}
            aria-label="Refresh"
          >
            Refresh
          </button>
        </div>
      </div>

      {/* ── Wikilinks tab ── */}
      {activeTab === 'wikilinks' && (
        <div className="graph-page__wikilinks">
          {nodeCount === 0 ? (
            <div className="graph-page__empty">
              <p>No notes in the graph yet.</p>
              <button
                className="graph-page__sync-btn"
                onClick={handleSyncVault}
                disabled={syncing}
                aria-label="Sync Vault"
              >
                {syncing ? 'Syncing\u2026' : 'Sync Vault'}
              </button>
            </div>
          ) : (
            <>
              <div className="graph-page__stats">
                <span className="graph-page__node-badge">
                  {nodeCount} nodes
                </span>
                <span className="graph-page__edge-badge">
                  {edgeCount} edges
                </span>
              </div>
              <Suspense fallback={
                <div className="graph-page__canvas-loading">Loading graph\u2026</div>
              }>
                <ForceGraph2D
                  graphData={forceGraphData}
                  nodeLabel="name"
                  onNodeClick={(node) => {
                    const n = allNodes.find((x) => x.id === (node as { id: string }).id);
                    if (n) setSelectedNode(n);
                  }}
                />
              </Suspense>
            </>
          )}

          {/* Selected node panel */}
          {selectedNode && (
            <div className="graph-page__side-panel">
              <button
                className="graph-page__side-panel-close"
                onClick={() => setSelectedNode(null)}
                aria-label="Close note panel"
              >
                \u00d7
              </button>
              <div className="graph-page__side-panel-title">{selectedNode.title}</div>
            </div>
          )}
        </div>
      )}

      {/* ── LightRAG Knowledge tab ── */}
      {activeTab === 'lightrag' && (
        <div className="graph-page__lightrag">
          {lrLoading && (
            <div role="status" className="graph-page__lr-loading">
              Loading entities\u2026
            </div>
          )}
          {lrError && (
            <div role="alert" className="graph-page__lr-error">
              LightRAG graph not available: {lrError}
            </div>
          )}
          {!lrLoading && !lrError && (
            <>
              <p className="graph-page__lr-count">
                {filteredEntities.length} entities
              </p>
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
                <p className="graph-page__lr-empty">
                  No LightRAG entities indexed yet.
                </p>
              )}
            </>
          )}
        </div>
      )}
    </div>
  );
}
