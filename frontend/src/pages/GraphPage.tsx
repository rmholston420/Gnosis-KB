/**
 * GraphPage.tsx
 * ============
 * Full-screen Cytoscape.js knowledge-graph visualisation.
 */

import React, { useEffect, useRef, useState, useCallback } from 'react';
import cytoscape from 'cytoscape';
import type { Core, EventObject } from 'cytoscape';
import type { GraphData, GraphNode, GraphEdge } from '../types';
import api from '../services/api';
import LightRagNodePanel, { type LightRagEntity, type LightRagRelation } from '../components/graph/LightRagNodePanel';
import './GraphPage.css';

// ---------------------------------------------------------------------------
// Constants
// ---------------------------------------------------------------------------
const NOTE_TYPE_COLORS: Record<string, string> = {
  permanent:   '#01696f',
  fleeting:    '#da7101',
  literature:  '#006494',
  journal:     '#7a39bb',
  map:         '#437a22',
  reference:   '#a13544',
  project:     '#964219',
  template:    '#7a7974',
};
const DEFAULT_COLOR = '#bab9b4';

const LAYOUTS = ['cose', 'breadthfirst', 'circle', 'grid', 'concentric'] as const;
type LayoutName = typeof LAYOUTS[number];

// ---------------------------------------------------------------------------
// Component
// ---------------------------------------------------------------------------
interface GraphPageProps {
  api?: typeof import('../services/api').default;
}

export default function GraphPage(_props: GraphPageProps) {
  const containerRef = useRef<HTMLDivElement>(null);
  const cyRef        = useRef<Core | null>(null);

  const [data,    setData]    = useState<GraphData | null>(null);
  const [loading, setLoading] = useState(true);
  const [error,   setError]   = useState<string | null>(null);

  const [selectedNodeId, setSelectedNodeId] = useState<string | null>(null);

  const [lightRagOpen,    setLightRagOpen]    = useState(false);
  const [lightRagNode,    setLightRagNode]    = useState<{ entity: LightRagEntity; relations: LightRagRelation[] } | null>(null);
  const [lightRagLoading, setLightRagLoading] = useState(false);
  const [lightRagError,   setLightRagError]   = useState<string | null>(null);

  const [layout, setLayout] = useState<LayoutName>('cose');
  const [search, setSearch] = useState('');

  // -------------------------------------------------------------------------
  // Data fetch
  // -------------------------------------------------------------------------
  useEffect(() => {
    api.getGraph()
      .then((d: unknown) => { setData(d as GraphData); setLoading(false); })
      .catch((e: unknown) => { setError(String(e)); setLoading(false); });
  }, []);

  const buildElements = useCallback(() => {
    if (!data) return [];

    const nodes = (data.nodes ?? []).map((n: GraphNode) => ({
      data: {
        id:    n.id,
        label: n.title,
        color: NOTE_TYPE_COLORS[n.note_type ?? ''] ?? DEFAULT_COLOR,
        type:  n.note_type ?? 'unknown',
      },
    }));

    const edges = (data.edges ?? []).map((e: GraphEdge) => ({
      data: {
        id:     `${e.source}-${e.target}`,
        source: e.source,
        target: e.target,
        label:  e.link_text ?? '',
      },
    }));

    return [...nodes, ...edges];
  }, [data]);

  // -------------------------------------------------------------------------
  // LightRAG node open — defined before Cytoscape useEffect so it can be
  // included in the dependency array without causing a lint warning.
  // -------------------------------------------------------------------------
  const handleLightRagOpen = useCallback(async (nodeId: string) => {
    setLightRagOpen(true);
    setLightRagLoading(true);
    setLightRagError(null);
    try {
      const result = await api.getLightRagNode(nodeId) as { entity: LightRagEntity; relations: LightRagRelation[] };
      setLightRagNode(result);
    } catch (e) {
      setLightRagError(String(e));
    } finally {
      setLightRagLoading(false);
    }
  }, []);

  // -------------------------------------------------------------------------
  // Cytoscape initialisation / re-render
  // -------------------------------------------------------------------------
  useEffect(() => {
    if (!data || !containerRef.current) return;

    if (cyRef.current) {
      cyRef.current.destroy();
      cyRef.current = null;
    }

    const cy = cytoscape({
      container: containerRef.current,
      elements:  buildElements(),
      style: [
        {
          selector: 'node',
          style: {
            'background-color':    'data(color)',
            'width':               '28px',
            'height':              '28px',
            'label':               'data(label)',
            'font-size':           '10px',
            'color':               '#28251d',
            'text-valign':         'bottom' as const,
            'text-halign':         'center' as const,
            'text-margin-y':       4,
            'text-outline-color':  '#f7f6f2',
            'text-outline-width':  2,
            'border-width':        1.5,
            'border-color':        'data(color)',
            'border-opacity':      0.6,
            'transition-property': 'background-color, border-color, width, height',
            'transition-duration': '200ms',
          } as unknown as cytoscape.Css.Node,
        },
        {
          selector: 'node:selected',
          style: {
            'width':        '38px',
            'height':       '38px',
            'border-width': 3,
            'border-color': '#01696f',
          },
        },
        {
          selector: 'node:active',
          style: { 'overlay-opacity': 0 },
        },
        {
          selector: 'edge',
          style: {
            'width':               1.5,
            'line-color':          '#dcd9d5',
            'target-arrow-color':  '#dcd9d5',
            'target-arrow-shape':  'triangle' as const,
            'curve-style':         'bezier' as const,
            'arrow-scale':         0.8,
            'transition-property': 'line-color, width',
            'transition-duration': '200ms',
          } as unknown as cytoscape.Css.Edge,
        },
        {
          selector: 'edge:selected',
          style: {
            'line-color':         '#01696f',
            'target-arrow-color': '#01696f',
            'width':              2.5,
          },
        },
      ],
      layout: { name: layout, animate: false, padding: 40 },
      minZoom: 0.1,
      maxZoom: 4,
      wheelSensitivity: 0.3,
    });

    cyRef.current = cy;

    cy.on('tap', 'node', (evt: EventObject) => {
      const node = evt.target;
      setSelectedNodeId(node.id());
    });

    cy.on('tap', 'node', (evt: EventObject) => {
      if ((evt.type as string) === 'dblTap') {
        const node = evt.target;
        handleLightRagOpen(node.id());
      }
    });

    cy.on('tap', (evt: EventObject) => {
      if (evt.target === cy) setSelectedNodeId(null);
    });

    return () => {
      cy.destroy();
      cyRef.current = null;
    };
  }, [data, layout, buildElements, handleLightRagOpen]);

  // -------------------------------------------------------------------------
  // Layout change
  // -------------------------------------------------------------------------
  const handleLayoutChange = useCallback((name: LayoutName) => {
    setLayout(name);
    if (cyRef.current) {
      cyRef.current.layout({ name, animate: true, padding: 40 }).run();
    }
  }, []);

  // -------------------------------------------------------------------------
  // Search / jump-to-node
  // -------------------------------------------------------------------------
  const handleSearch = useCallback((q: string) => {
    setSearch(q);
    if (!cyRef.current || !q.trim()) return;
    const match = cyRef.current.nodes().filter(
      (n) => n.data('label')?.toLowerCase().includes(q.toLowerCase()),
    );
    if (match.length) {
      cyRef.current.animate({ fit: { eles: match, padding: 80 }, duration: 400 });
      match.first().select();
      setSelectedNodeId(match.first().id());
    }
  }, []);

  // -------------------------------------------------------------------------
  // Selected node
  // -------------------------------------------------------------------------
  const selectedNode = selectedNodeId
    ? (data?.nodes ?? []).find((n: GraphNode) => n.id === selectedNodeId)
    : null;

  // -------------------------------------------------------------------------
  // Stats
  // -------------------------------------------------------------------------
  const nodeCount = data?.nodes?.length ?? 0;
  const edgeCount = data?.edges?.length ?? 0;

  // -------------------------------------------------------------------------
  // Render
  // -------------------------------------------------------------------------
  if (loading) {
    return (
      <div className="graph-page graph-page--loading">
        <span className="graph-page__spinner" aria-label="Loading graph" />
      </div>
    );
  }

  if (error) {
    return (
      <div className="graph-page graph-page--error" role="alert">
        <p>Failed to load graph: {error}</p>
        <button onClick={() => window.location.reload()}>Retry</button>
      </div>
    );
  }

  return (
    <div className="graph-page">
      {/* Toolbar */}
      <div className="graph-page__toolbar" role="toolbar" aria-label="Graph controls">
        <div className="graph-page__toolbar-group">
          {LAYOUTS.map((l) => (
            <button
              key={l}
              className={`graph-page__layout-btn${
                l === layout ? ' graph-page__layout-btn--active' : ''
              }`}
              onClick={() => handleLayoutChange(l)}
              aria-pressed={l === layout}
            >
              {l}
            </button>
          ))}
        </div>

        <input
          className="graph-page__search"
          type="search"
          placeholder="Jump to node\u2026"
          value={search}
          onChange={(e) => handleSearch(e.target.value)}
          aria-label="Search nodes"
        />

        <span className="graph-page__stats" aria-label={`${nodeCount} nodes, ${edgeCount} edges`}>
          {nodeCount} nodes \u00b7 {edgeCount} edges
        </span>
      </div>

      {/* Graph canvas */}
      <div className="graph-page__canvas-wrap">
        <div ref={containerRef} className="graph-page__canvas" aria-label="Knowledge graph" />
      </div>

      {/* Selected node side panel */}
      {selectedNode && (
        <div className="graph-page__side-panel">
          <button
            className="graph-page__side-panel-close"
            onClick={() => setSelectedNodeId(null)}
            aria-label="Close note panel"
          >
            \u00d7
          </button>
          <div className="graph-page__side-panel-title">{selectedNode.title}</div>
          <button
            className="graph-page__lightrag-btn"
            onClick={() => handleLightRagOpen(selectedNode.id)}
            aria-label="Open LightRAG panel"
          >
            Open in LightRAG
          </button>
        </div>
      )}

      {/* LightRAG panel */}
      {lightRagOpen && lightRagNode && (
        <LightRagNodePanel
          entity={lightRagNode.entity}
          relations={lightRagNode.relations}
          notes={[]}
          onClose={() => setLightRagOpen(false)}
          onNavigateToNote={(noteId) => { setSelectedNodeId(noteId); setLightRagOpen(false); }}
        />
      )}
      {lightRagOpen && lightRagLoading && (
        <div className="lightrag-loading" role="status">Loading LightRAG data\u2026</div>
      )}
      {lightRagOpen && lightRagError && (
        <div className="lightrag-error" role="alert">{lightRagError}</div>
      )}
    </div>
  );
}
