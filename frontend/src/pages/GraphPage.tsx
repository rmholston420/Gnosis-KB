import React, { useEffect, useRef, useState, useCallback } from 'react';
import { useNavigate } from 'react-router-dom';
import cytoscape from 'cytoscape';
import fcose from 'cytoscape-fcose';
import api from '../services/api';
import type { GraphData, GraphNode, GraphEdge } from '../types';
import LightRagNodePanel, { type LightRagEntity, type LightRagRelation } from '../components/graph/LightRagNodePanel';

cytoscape.use(fcose);

type ColorBy = 'type' | 'status' | 'folder';
type SizeBy = 'word_count' | 'tag_count' | 'incoming' | 'outgoing';
type LayoutName = 'fcose' | 'circle' | 'grid' | 'breadthfirst';

const TYPE_COLORS: Record<string, string> = {
  permanent: '#4a9eff',
  fleeting: '#f0a500',
  literature: '#22c55e',
  moc: '#a855f7',
};

const STATUS_COLORS: Record<string, string> = {
  draft: '#94a3b8',
  'in-progress': '#f59e0b',
  evergreen: '#22c55e',
};

function getNodeColor(node: GraphNode, colorBy: ColorBy, folderColors: Map<string, string>): string {
  if (colorBy === 'type') return TYPE_COLORS[node.note_type] ?? '#64748b';
  if (colorBy === 'status') return STATUS_COLORS[node.status] ?? '#64748b';
  if (colorBy === 'folder') return folderColors.get(node.folder) ?? '#64748b';
  return '#64748b';
}

function getNodeSize(node: GraphNode, sizeBy: SizeBy): number {
  const base = 24;
  if (sizeBy === 'word_count') return base + Math.sqrt(node.word_count ?? 0) * 0.4;
  if (sizeBy === 'tag_count') return base + (node.tag_count ?? 0) * 3;
  if (sizeBy === 'incoming') return base + (node.incoming_link_count ?? 0) * 4;
  if (sizeBy === 'outgoing') return base + (node.outgoing_link_count ?? 0) * 4;
  return base;
}

function buildFolderColors(nodes: GraphNode[]): Map<string, string> {
  const palette = ['#f43f5e','#f97316','#eab308','#22c55e','#06b6d4','#6366f1','#d946ef','#14b8a6'];
  const folders = [...new Set(nodes.map(n => n.folder).filter(Boolean))];
  const m = new Map<string, string>();
  folders.forEach((f, i) => m.set(f, palette[i % palette.length]));
  return m;
}

interface GraphPageProps {
  onNodeSelect?: (id: string | null) => void;
}

export default function GraphPage({ onNodeSelect }: GraphPageProps) {
  const containerRef = useRef<HTMLDivElement>(null);
  const cyRef = useRef<cytoscape.Core | null>(null);
  const navigate = useNavigate();

  const [data, setData] = useState<GraphData | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const [colorBy, setColorBy] = useState<ColorBy>('type');
  const [sizeBy, setSizeBy] = useState<SizeBy>('word_count');
  const [layout, setLayout] = useState<LayoutName>('fcose');
  const [query, setQuery] = useState('');
  const [minLinks, setMinLinks] = useState(0);

  // LightRAG panel state
  const [lightRagOpen, setLightRagOpen] = useState(false);
  const [lightRagNode, setLightRagNode] = useState<{ entity: LightRagEntity; relations: LightRagRelation[] } | null>(null);
  const [lightRagLoading, setLightRagLoading] = useState(false);
  const [lightRagError, setLightRagError] = useState<string | null>(null);

  // Selected node id for info panel
  const [selectedNodeId, setSelectedNodeId] = useState<string | null>(null);

  useEffect(() => {
    api.getGraph()
      .then(d => { setData(d); setLoading(false); })
      .catch(e => { setError(String(e)); setLoading(false); });
  }, []);

  const buildElements = useCallback(() => {
    if (!data) return [];
    const folderColors = buildFolderColors(data.nodes);
    const q = query.toLowerCase().trim();

    const visibleNodes = data.nodes.filter(n => {
      const totalLinks = (n.incoming_link_count ?? 0) + (n.outgoing_link_count ?? 0);
      if (totalLinks < minLinks) return false;
      if (q && !n.title.toLowerCase().includes(q)) return false;
      return true;
    });
    const visibleIds = new Set(visibleNodes.map(n => n.id));

    const nodeEls = visibleNodes.map(n => ({
      data: {
        id: n.id,
        label: n.title,
        color: getNodeColor(n, colorBy, folderColors),
        size: getNodeSize(n, sizeBy),
        note: n,
      },
    }));

    const edgeEls = data.edges
      .filter(e => visibleIds.has(e.source) && visibleIds.has(e.target))
      .map(e => ({
        data: {
          id: `${e.source}-${e.target}`,
          source: e.source,
          target: e.target,
          label: e.link_text ?? '',
        },
      }));

    return [...nodeEls, ...edgeEls];
  }, [data, colorBy, sizeBy, query, minLinks]);

  useEffect(() => {
    if (!containerRef.current || !data) return;

    if (cyRef.current) cyRef.current.destroy();

    const elements = buildElements();

    const cy = cytoscape({
      container: containerRef.current,
      elements,
      style: [
        {
          selector: 'node',
          style: {
            'background-color': 'data(color)',
            'width': 'data(size)',
            'height': 'data(size)',
            'label': 'data(label)',
            'font-size': '11px',
            'color': '#f1f5f9',
            'text-valign': 'bottom',
            'text-halign': 'center',
            'text-margin-y': 4,
            'text-outline-color': '#0f172a',
            'text-outline-width': 1,
            'border-width': 1.5,
            'border-color': 'rgba(255,255,255,0.15)',
            'transition-property': 'background-color width height border-width',
            'transition-duration': '200ms',
          } as cytoscape.Css.Node,
        },
        {
          selector: 'node:selected',
          style: {
            'border-width': 3,
            'border-color': '#f8fafc',
            'width': (ele: cytoscape.NodeSingular) => (ele.data('size') as number) * 1.4,
            'height': (ele: cytoscape.NodeSingular) => (ele.data('size') as number) * 1.4,
          } as cytoscape.Css.Node,
        },
        {
          selector: 'edge',
          style: {
            'width': 1.5,
            'line-color': 'rgba(148,163,184,0.35)',
            'target-arrow-color': 'rgba(148,163,184,0.5)',
            'target-arrow-shape': 'triangle',
            'curve-style': 'bezier',
            'arrow-scale': 0.7,
            'transition-property': 'line-color width',
            'transition-duration': '200ms',
          } as cytoscape.Css.Edge,
        },
        {
          selector: 'edge:selected',
          style: {
            'line-color': '#4a9eff',
            'width': 2.5,
            'target-arrow-color': '#4a9eff',
          } as cytoscape.Css.Edge,
        },
        {
          selector: '.faded',
          style: { 'opacity': 0.15 } as cytoscape.Css.Node & cytoscape.Css.Edge,
        },
      ],
      layout: {
        name: layout === 'fcose' ? 'fcose' : layout,
        animate: true,
        animationDuration: 500,
        ...(layout === 'fcose' ? {
          randomize: false,
          quality: 'default',
          nodeRepulsion: 4500,
          idealEdgeLength: 100,
          edgeElasticity: 0.45,
          numIter: 2500,
          nodeSeparation: 75,
        } : {}),
      } as cytoscape.LayoutOptions,
      minZoom: 0.05,
      maxZoom: 4,
      wheelSensitivity: 0.3,
    });

    // Node tap → select or navigate
    cy.on('tap', 'node', evt => {
      const nodeId: string = evt.target.id() as string;
      const node: GraphNode = evt.target.data('note') as GraphNode;
      setSelectedNodeId(nodeId);
      onNodeSelect?.(nodeId);

      // Highlight neighbors
      cy.elements().addClass('faded');
      const neighborhood = evt.target.closedNeighborhood();
      neighborhood.removeClass('faded');
    });

    // Double-tap → navigate to note
    cy.on('dblTap tap', 'node', (evt) => {
      if (evt.type === 'dblTap') {
        const node: GraphNode = evt.target.data('note') as GraphNode;
        navigate(`/notes/${node.id}`);
      }
    });

    // Background tap → clear selection
    cy.on('tap', (evt) => {
      if (evt.target === cy) {
        cy.elements().removeClass('faded');
        setSelectedNodeId(null);
        onNodeSelect?.(null);
      }
    });

    cyRef.current = cy;

    return () => {
      cy.destroy();
    };
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [data, colorBy, sizeBy, layout, query, minLinks]);

  // LightRAG node fetch
  const handleLightRagOpen = useCallback(async (nodeId: string) => {
    setLightRagOpen(true);
    setLightRagLoading(true);
    setLightRagError(null);
    try {
      const result = await api.getLightRagNode(nodeId);
      setLightRagNode(result);
    } catch (e) {
      setLightRagError(String(e));
    } finally {
      setLightRagLoading(false);
    }
  }, []);

  const selectedNode = data?.nodes.find(n => n.id === selectedNodeId) ?? null;

  if (loading) {
    return (
      <div className="flex items-center justify-center h-full">
        <div className="text-slate-400 text-sm animate-pulse">Loading graph…</div>
      </div>
    );
  }

  if (error) {
    return (
      <div className="flex items-center justify-center h-full">
        <div className="text-red-400 text-sm">Error loading graph: {error}</div>
      </div>
    );
  }

  return (
    <div className="flex flex-col h-full bg-slate-900 text-slate-100">
      {/* Toolbar */}
      <div className="flex flex-wrap items-center gap-3 px-4 py-2 bg-slate-800/80 border-b border-slate-700/60 backdrop-blur-sm">
        <span className="text-xs font-semibold text-slate-400 uppercase tracking-widest">Graph</span>

        <div className="flex items-center gap-2">
          <label className="text-xs text-slate-400">Color</label>
          <select
            value={colorBy}
            onChange={e => setColorBy(e.target.value as ColorBy)}
            className="text-xs bg-slate-700 border border-slate-600 rounded px-2 py-0.5 text-slate-200"
          >
            <option value="type">Type</option>
            <option value="status">Status</option>
            <option value="folder">Folder</option>
          </select>
        </div>

        <div className="flex items-center gap-2">
          <label className="text-xs text-slate-400">Size</label>
          <select
            value={sizeBy}
            onChange={e => setSizeBy(e.target.value as SizeBy)}
            className="text-xs bg-slate-700 border border-slate-600 rounded px-2 py-0.5 text-slate-200"
          >
            <option value="word_count">Word Count</option>
            <option value="tag_count">Tags</option>
            <option value="incoming">Incoming Links</option>
            <option value="outgoing">Outgoing Links</option>
          </select>
        </div>

        <div className="flex items-center gap-2">
          <label className="text-xs text-slate-400">Layout</label>
          <select
            value={layout}
            onChange={e => setLayout(e.target.value as LayoutName)}
            className="text-xs bg-slate-700 border border-slate-600 rounded px-2 py-0.5 text-slate-200"
          >
            <option value="fcose">Force (fCoSE)</option>
            <option value="circle">Circle</option>
            <option value="grid">Grid</option>
            <option value="breadthfirst">Tree</option>
          </select>
        </div>

        <div className="flex items-center gap-2">
          <label className="text-xs text-slate-400">Min links</label>
          <input
            type="number"
            min={0}
            value={minLinks}
            onChange={e => setMinLinks(Number(e.target.value))}
            className="text-xs w-14 bg-slate-700 border border-slate-600 rounded px-2 py-0.5 text-slate-200"
          />
        </div>

        <div className="flex items-center gap-2 ml-auto">
          <input
            type="search"
            placeholder="Filter nodes…"
            value={query}
            onChange={e => setQuery(e.target.value)}
            className="text-xs bg-slate-700 border border-slate-600 rounded px-2 py-0.5 text-slate-200 w-40 placeholder:text-slate-500"
          />
        </div>
      </div>

      {/* Main content */}
      <div className="flex flex-1 min-h-0">
        {/* Canvas */}
        <div ref={containerRef} className="flex-1 min-h-0" />

        {/* Side panel — selected node info */}
        {selectedNode && (
          <div className="w-64 border-l border-slate-700/60 bg-slate-800/60 p-4 overflow-y-auto text-sm">
            <div className="flex items-start justify-between mb-3">
              <h3 className="font-semibold text-slate-100 leading-snug">{selectedNode.title}</h3>
              <button
                onClick={() => { setSelectedNodeId(null); onNodeSelect?.(null); }}
                className="text-slate-500 hover:text-slate-300 ml-2 shrink-0"
                aria-label="Close panel"
              >✕</button>
            </div>

            <div className="space-y-1 text-slate-400 text-xs mb-4">
              <div><span className="text-slate-500">Type:</span> {selectedNode.note_type}</div>
              <div><span className="text-slate-500">Status:</span> {selectedNode.status}</div>
              {selectedNode.folder && <div><span className="text-slate-500">Folder:</span> {selectedNode.folder}</div>}
              <div><span className="text-slate-500">Words:</span> {selectedNode.word_count ?? 0}</div>
              <div><span className="text-slate-500">Incoming:</span> {selectedNode.incoming_link_count ?? 0}</div>
              <div><span className="text-slate-500">Outgoing:</span> {selectedNode.outgoing_link_count ?? 0}</div>
            </div>

            <div className="flex flex-col gap-2">
              <button
                onClick={() => navigate(`/notes/${selectedNode.id}`)}
                className="w-full text-xs bg-blue-600 hover:bg-blue-500 text-white rounded px-3 py-1.5 transition-colors"
              >
                Open Note
              </button>
              <button
                onClick={() => handleLightRagOpen(selectedNode.id)}
                className="w-full text-xs bg-purple-700 hover:bg-purple-600 text-white rounded px-3 py-1.5 transition-colors"
              >
                LightRAG View
              </button>
            </div>
          </div>
        )}
      </div>

      {/* LightRAG panel */}
      {lightRagOpen && (
        <LightRagNodePanel
          data={lightRagNode}
          loading={lightRagLoading}
          error={lightRagError}
          onClose={() => setLightRagOpen(false)}
        />
      )}
    </div>
  );
}
