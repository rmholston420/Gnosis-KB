/**
 * GraphView2D — react-force-graph-2d wrapper.
 * Renders the vault knowledge graph as a WebGL-accelerated force-directed canvas.
 * Accepts external nodes/links/highlightIds so GraphPage controls filtering.
 * Exposes a ForwardRef so GraphPage can drive zoom/center via graphRef.
 */
import React, { useRef, useCallback } from 'react';
import ForceGraph2D, { type ForceGraphMethods, type NodeObject, type LinkObject } from 'react-force-graph-2d';
import { nodeColor, nodeVal, NODE_COLORS } from '../../lib/graphUtils';
import type { GraphNode } from '../../types';

export interface ForceNode extends NodeObject {
  id:                  string;
  title:               string;
  type:                string;
  incoming_link_count: number;
  cluster_id?:         number;
  x?: number;
  y?: number;
}

export interface ForceLink extends LinkObject {
  source: string | ForceNode;
  target: string | ForceNode;
  type:   string;
}

interface GraphView2DProps {
  nodes:          ForceNode[];
  links:          ForceLink[];
  highlightIds?:  Set<string>;
  clusterMode?:   boolean;
  showLabels?:    boolean;
  onNodeClick?:   (node: ForceNode) => void;
  onNodeHover?:   (node: ForceNode | null) => void;
  width?:         number;
  height?:        number;
}

/** Map cluster index to a color string. */
function clusterColor(idx?: number): string {
  const palette = Object.values(NODE_COLORS);
  return palette[(idx ?? 0) % palette.length] as string;
}

/**
 * GraphView2D renders the knowledge graph.
 * Node color encodes note type; node size encodes incoming link count.
 */
export const GraphView2D = React.forwardRef<
  ForceGraphMethods | undefined,
  GraphView2DProps
>(
  ({ nodes, links, highlightIds, clusterMode, showLabels = true, onNodeClick, onNodeHover, width, height }, ref) => {

    const internalRef = useRef<ForceGraphMethods | undefined>(undefined);
    const resolvedRef = (ref ?? internalRef) as React.MutableRefObject<ForceGraphMethods | undefined>;

    const getNodeColor = useCallback((node: NodeObject) => {
      const n = node as ForceNode;
      if (highlightIds && highlightIds.size > 0) {
        if (!highlightIds.has(n.id)) return 'rgba(100,100,100,0.15)';
      }
      if (clusterMode) return clusterColor(n.cluster_id);
      return nodeColor(n as unknown as GraphNode);
    }, [highlightIds, clusterMode]);

    const getNodeVal = useCallback((node: NodeObject) => {
      return nodeVal(node as unknown as GraphNode);
    }, []);

    const handleNodeClick = useCallback((node: NodeObject) => {
      onNodeClick?.(node as ForceNode);
    }, [onNodeClick]);

    const handleNodeHover = useCallback((node: NodeObject | null) => {
      onNodeHover?.(node as ForceNode | null);
    }, [onNodeHover]);

    const paintNode = useCallback((
      node: NodeObject,
      ctx: CanvasRenderingContext2D,
      globalScale: number,
    ) => {
      const n    = node as ForceNode;
      const x    = n.x ?? 0;
      const y    = n.y ?? 0;
      const r    = Math.sqrt(getNodeVal(node)) * 1.5;
      const col  = getNodeColor(node);

      ctx.beginPath();
      ctx.arc(x, y, r, 0, 2 * Math.PI);
      ctx.fillStyle = col;
      ctx.fill();

      if (showLabels && globalScale >= 1.2) {
        const fontSize = Math.max(8 / globalScale, 3);
        ctx.font = `${fontSize}px Inter,sans-serif`;
        ctx.fillStyle = '#e6edf3';
        ctx.textAlign = 'center';
        ctx.textBaseline = 'middle';
        ctx.fillText(n.title?.slice(0, 30) ?? '', x, y + r + fontSize);
      }
    }, [getNodeColor, getNodeVal, showLabels]);

    return (
      <ForceGraph2D
        ref={resolvedRef}
        graphData={{ nodes, links }}
        nodeColor={getNodeColor}
        nodeVal={getNodeVal}
        linkWidth={(link) => (link as ForceLink).type === 'wikilink' ? 1 : 0.5}
        linkDirectionalArrowLength={3}
        linkDirectionalArrowRelPos={1}
        linkColor={() => 'rgba(100,150,200,0.35)'}
        nodeCanvasObject={paintNode}
        nodeCanvasObjectMode={() => 'replace'}
        onNodeClick={handleNodeClick}
        onNodeHover={handleNodeHover}
        nodeLabel={(node) => (node as ForceNode).title ?? ''}
        enableNodeDrag
        cooldownTicks={100}
        width={width}
        height={height}
        backgroundColor="#0d1117"
      />
    );
  },
);

GraphView2D.displayName = 'GraphView2D';
export default GraphView2D;
