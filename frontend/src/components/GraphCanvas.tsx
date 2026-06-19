/**
 * GraphCanvas: Cytoscape.js force-directed knowledge graph.
 */

import { useEffect, useRef } from 'react';
import cytoscape from 'cytoscape';
// cytoscape-fcose has no bundled types — use require to bypass TS module resolution
// eslint-disable-next-line @typescript-eslint/no-require-imports
const fcose = require('cytoscape-fcose');
import { useNavigate } from 'react-router-dom';
import type { GraphData, NoteType } from '../types';

cytoscape.use(fcose);

const NOTE_TYPE_COLOR: Record<NoteType | string, string> = {
  permanent: '#58a6ff',
  fleeting: '#3fb950',
  literature: '#d2a8ff',
  journal: '#ffa657',
  map: '#79c0ff',
  reference: '#f78166',
  project: '#e3b341',
  template: '#8b949e',
};

interface GraphCanvasProps {
  data: GraphData;
  height?: string;
  onNodeClick?: (noteId: string) => void;
}

export default function GraphCanvas({ data, height = '100%', onNodeClick }: GraphCanvasProps) {
  const containerRef = useRef<HTMLDivElement>(null);
  const cyRef = useRef<cytoscape.Core | null>(null);
  const navigate = useNavigate();

  useEffect(() => {
    if (!containerRef.current) return;

    const elements: cytoscape.ElementDefinition[] = [
      ...data.nodes.map((n) => ({
        data: {
          id: n.id,
          label: n.title.length > 30 ? n.title.slice(0, 30) + '...' : n.title,
          noteType: n.note_type,
          inLinks: n.incoming_link_count,
          size: Math.max(20, Math.min(60, 20 + n.incoming_link_count * 4)),
        },
      })),
      ...data.edges.map((e, i) => ({
        data: {
          id: `e-${i}`,
          source: e.source,
          target: e.target,
          label: e.link_text,
        },
      })),
    ];

    const cy = cytoscape({
      container: containerRef.current,
      elements,
      style: [
        {
          selector: 'node',
          style: {
            'background-color': (ele: cytoscape.NodeSingular) =>
              NOTE_TYPE_COLOR[ele.data('noteType')] || '#8b949e',
            'label': 'data(label)',
            'color': '#e6edf3',
            'font-size': '10px',
            'text-valign': 'bottom',
            'text-halign': 'center',
            'text-margin-y': 4,
            'width': 'data(size)',
            'height': 'data(size)',
            'border-width': 1,
            'border-color': '#30363d',
          },
        },
        {
          selector: 'edge',
          style: {
            'width': 1,
            'line-color': '#30363d',
            'target-arrow-color': '#30363d',
            'target-arrow-shape': 'triangle',
            'curve-style': 'bezier',
            'opacity': 0.6,
          },
        },
        {
          selector: 'node:selected',
          style: {
            'border-width': 2,
            'border-color': '#58a6ff',
          },
        },
      ],
      layout: {
        name: 'fcose',
        animate: true,
        animationDuration: 600,
        fit: true,
        padding: 30,
        randomize: false,
      } as cytoscape.LayoutOptions,
    });

    cy.on('dblclick', 'node', (e) => {
      const nodeId = e.target.data('id');
      if (onNodeClick) onNodeClick(nodeId);
      else navigate(`/notes/${nodeId}`);
    });

    cy.on('mouseover', 'node', (e) => {
      e.target.style({ 'border-width': 2, 'border-color': '#58a6ff' });
    });
    cy.on('mouseout', 'node', (e) => {
      if (!e.target.selected()) {
        e.target.style({ 'border-width': 1, 'border-color': '#30363d' });
      }
    });

    cyRef.current = cy;

    return () => {
      cy.destroy();
      cyRef.current = null;
    };
  }, [data]);

  return (
    <div className="relative" style={{ height }}>
      <div ref={containerRef} style={{ width: '100%', height: '100%' }} />
      <div className="absolute bottom-4 left-4 bg-bg-secondary border border-border rounded p-2 text-xs space-y-1">
        {Object.entries(NOTE_TYPE_COLOR).map(([type, color]) => (
          <div key={type} className="flex items-center gap-1.5">
            <div className="w-2.5 h-2.5 rounded-full flex-shrink-0" style={{ backgroundColor: color }} />
            <span className="text-text-secondary capitalize">{type}</span>
          </div>
        ))}
      </div>
    </div>
  );
}
