/**
 * GraphPage.tsx
 * Tab-based knowledge-graph page using TanStack Query.
 *
 * Tab 1 — Wikilinks:          react-force-graph-2d visualisation
 * Tab 2 — LightRAG Knowledge: entity list + lightrag graph health check
 *
 * NOTE: tab buttons have NO role="tab" — tests query them via
 * getByRole('button', { name: /wikilinks/i }). An explicit role="tab"
 * would override the implicit button role and break those queries.
 */

import React, { useState, useCallback, lazy, Suspense } from 'react';
import { useQuery, useQueryClient } from '@tanstack/react-query';
import type { GraphData, GraphNode } from '../types';
import api from '../services/api';
import type { GraphEntitySummary } from '../services/api';
import './GraphPage.css';

const ForceGraph2D = lazy(() => import('react-force-graph-2d'));

type Tab = 'wikilinks' | 'lightrag';

interface LightRagData {
  entities: GraphEntitySummary[];
  relations?: unknown[];
}

export default function GraphPage() {
  const queryClient = useQueryClient();

  const [activeTab,    setActiveTab]    = useState<Tab>('wikilinks');
  const [nodeFilter,   setNodeFilter]   = useState('');
  const [entityFilter, setEntityFilter] = useState('');
  const [selectedNode, setSelectedNode] = useState<GraphNode | null>(null);
  const [syncing,      setSyncing]      = useState(false);

  // ── Wikilinks graph ────────────────────────────────────────────────────
  const {
    data: graphData,
    isLoading: graphLoading,
    isError: graphIsError,
    error: graphError,
  } = useQuery<GraphData>({
    queryKey: ['graph'],
    queryFn: () => api.getFullGraph() as Promise<GraphData>,
    retry: false,
  });

  // ── LightRAG: graph health check (/graph/lightrag) ─────────────────────
  // This query is the canary: if the lightrag backend is unavailable the
  // endpoint returns non-2xx and request() throws, surfacing lrGraphIsError.
  const {
    isLoading: lrGraphLoading,
    isError:   lrGraphIsError,
    error:     lrGraphError,
  } = useQuery({
    queryKey: ['lightrag-graph'],
    queryFn: () => api.getLightRagGraph(),
    enabled: activeTab === 'lightrag',
    retry: false,
  });

  // ── LightRAG: entity list (/graph/entities) ────────────────────────────
  const {
    data: lrData,
    isLoading: lrEntitiesLoading,
    isError:   lrEntitiesIsError,
    error:     lrEntitiesError,
  } = useQuery<LightRagData>({
    queryKey: ['graph-entities'],
    queryFn: () => api.getGraphEntities() as Promise<LightRagData>,
    enabled: activeTab === 'lightrag',
    retry: false,
  });

  // Merged LightRAG loading / error state
  const lrLoading = lrGraphLoading || lrEntitiesLoading;
  const lrIsError = lrGraphIsError || lrEntitiesIsError;
  const lrError   = lrGraphError   ?? lrEntitiesError;

  // ── Handlers ───────────────────────────────────────────────────────────
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

  // ── Derived ────────────────────────────────────────────────────────────
  const allNodes  = graphData?.nodes ?? [];
  const nodeCount = allNodes.length;
  const edgeCount = graphData?.edges?.length ?? 0;

  const filteredNodes = nodeFilter.trim()
    ? allNodes.filter((n) => n.title?.toLowerCase().includes(nodeFilter.toLowerCase()))
    : allNodes;

  const allEntities = lrData?.entities ?? [];
  const filteredEntities = entityFilter.trim()
    ? allEntities.filter((e) =>
        e.id?.toLowerCase().includes(entityFilter.toLowerCase()) ||
        e.label?.toLowerCase().includes(entityFilter.toLowerCase())
      )
    : allEntities;

  const forceGraphData = {
    nodes: filteredNodes.map((n) => ({ id: n.id, name: n.title, type: n.note_type })),
    links: (graphData?.edges ?? []).map((e) => ({ source: e.source, target: e.target })),
  };

  // ── Render ─────────────────────────────────────────────────────────────
  return (
    <div className="graph-page">

      {/* Header — always in DOM, never behind a loading gate */}
      <div className="graph-page__header">
        <h1 className="graph-page__title">Knowledge Graph</h1>

        {/* Tab buttons — no role="tab"; tests query by role="button" */}
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

      {/* ── Wikilinks tab content ── */}
      {activeTab === 'wikilinks' && (
        <div className="graph-page__wikilinks">
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
          {!graphLoading && !graphIsError && nodeCount === 0 && (
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
          )}
          {!graphLoading && !graphIsError && nodeCount > 0 && (
            <>
              <div className="graph-page__stats">
                <span className="graph-page__node-badge">{nodeCount} nodes</span>
                <span className="graph-page__edge-badge">{edgeCount} edges</span>
              </div>
              <Suspense fallback={<div className="graph-page__canvas-loading">Loading graph\u2026</div>}>
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

      {/* ── LightRAG Knowledge tab content ── */}
      {activeTab === 'lightrag' && (
        <div className="graph-page__lightrag">
          {lrLoading && (
            <div role="status" className="graph-page__lr-loading">Loading entities\u2026</div>
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
