/**
 * GraphCanvas: Cytoscape.js force-directed knowledge graph.
 * Uses gnosis-* CSS token classes — NOT legacy bg-bg-primary classes.
 */

import { useEffect, useRef } from 'react';
import cytoscape from 'cytoscape';
// cytoscape-fcose has no bundled types — use require to bypass TS module resolution
// eslint-disable-next-line @typescript-eslint/no-var-requires
const fcose = require('cytoscape-fcose');
import { useNavigate } from 'react-router-dom';
import type { GraphData, NoteType } from '../types';

cytoscape.use(fcose);

const NOTE_TYPE_COLORS: Record<NoteType | 'default', string> = {
  fleeting:   '#f59e0b',
  permanent:  '#4f9cf9',
  literature: '#10b981',
  journal:    '#f472b6',
  map:        '#a855f7',
  reference:  '#fb923c',
  project:    '#38bdf8',
  template:   '#6b7280',
  area:       '#84cc16',
  resource:   '#06b6d4',
  moc:        '#8b5cf6',
  default:    '#9ca3af',
};

interface GraphCanvasProps {
  data: GraphData;
  onNodeClick?: (id: string) => void;
}

export default function GraphCanvas({ data, onNodeClick }: GraphCanvasProps) {
  const containerRef = useRef<HTMLDivElement>(null);
  const cyRef        = useRef<cytoscape.Core | null>(null);
  const navigate     = useNavigate();

  useEffect(() => {
    if (!containerRef.current || !data) return;

    if (cyRef.current) {
      cyRef.current.destroy();
    }

    const elements: cytoscape.ElementDefinition[] = [
      ...data.nodes.map((n) => ({
        data: {
          id:    n.note_id ?? n.id,
          label: n.title,
          type:  n.note_type ?? n.type,
          color: NOTE_TYPE_COLORS[(n.note_type ?? n.type ?? 'default') as NoteType | 'default'] ?? NOTE_TYPE_COLORS.default,
          size:  Math.max(20, Math.sqrt((n.incoming_link_count ?? 0) + (n.outgoing_link_count ?? 0) + 1) * 12),
        },
      })),
      ...data.edges.map((e) => ({
        data: {
          id:     `${e.source_id ?? e.source}-${e.target_id ?? e.target}`,
          source: e.source_id ?? e.source,
          target: e.target_id ?? e.target,
          label:  e.link_text ?? '',
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
            'background-color':   'data(color)',
            'label':              'data(label)',
            'width':              'data(size)',
            'height':             'data(size)',
            'font-size':          '10px',
            'color':              '#e5e7eb',
            'text-valign':        'bottom',
            'text-halign':        'center',
            'text-margin-y':      4,
            'text-background-color': '#1f2937',
            'text-background-opacity': 0.7,
            'text-background-padding': '2px',
          },
        },
        {
          selector: 'edge',
          style: {
            'width':              1,
            'line-color':         '#374151',
            'target-arrow-color': '#374151',
            'target-arrow-shape': 'triangle',
            'curve-style':        'bezier',
            'opacity':            0.6,
          },
        },
        {
          selector: 'node:selected',
          style: { 'border-width': 2, 'border-color': '#4f9cf9' },
        },
        {
          selector: 'node:active',
          style: { 'overlay-opacity': 0.1 },
        },
      ],
      layout: {
        name:              'fcose',
        animate:           true,
        animationDuration: 600,
        nodeSep:           80,
        idealEdgeLength:   120,
        quality:           'default',
      } as cytoscape.LayoutOptions,
      userZoomingEnabled:  true,
      userPanningEnabled:  true,
      boxSelectionEnabled: false,
      minZoom: 0.1,
      maxZoom: 5,
    });

    cy.on('tap', 'node', (evt) => {
      const id = evt.target.id() as string;
      if (onNodeClick) {
        onNodeClick(id);
      } else {
        navigate(`/notes/${id}`);
      }
    });

    cyRef.current = cy;

    return () => {
      cy.destroy();
    };
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [data]);

  return (
    <div
      ref={containerRef}
      className="h-full w-full bg-gnosis-bg"
      style={{ minHeight: '400px' }}
    />
  );
}
