/**
 * GraphView2D — react-force-graph-2d wrapper.
 * Renders the full vault knowledge graph with clustering, node labels,
 * hover highlights, and click-to-focus behaviour.
 */
import React, { useRef, useCallback, useState } from 'react';
import ForceGraph2D, { type ForceGraphMethods } from 'react-force-graph-2d';
import { useFullGraph } from '../../hooks/useGraph';
import { toForceGraphData, nodeColor, nodeVal } from '../../lib/graphUtils';
import type { GraphNode } from '../../types';

interface Props {
  onNodeClick?: (node: GraphNode) => void;
  onError?: (err: Error) => void;
  width?:  number;
  height?: number;
}

export function GraphView2D({ onNodeClick, onError, width = 800, height = 600 }: Props) {
  const fgRef = useRef<ForceGraphMethods | undefined>(undefined);
  const { data: rawGraph, isLoading, isError, error } = useFullGraph();
  const [hovered, setHovered] = useState<string | null>(null);

  // Propagate query errors to parent (GraphPage) so it can render error state
  React.useEffect(() => {
    if (isError && error && onError) {
      onError(error as Error);
    }
  }, [isError, error, onError]);

  const graphData = rawGraph ? toForceGraphData(rawGraph) : { nodes: [], links: [] };

  const handleNodeClick = useCallback(
    (node: unknown) => {
      const n = node as GraphNode & { id: string };
      fgRef.current?.centerAt(n.x, n.y, 800);
      fgRef.current?.zoom(4, 800);
      onNodeClick?.(n);
    },
    [onNodeClick],
  );

  if (isLoading) {
    return (
      <div className="flex items-center justify-center" style={{ width, height }}>
        <span className="text-gnosis-muted text-sm">Loading graph…</span>
      </div>
    );
  }

  // Error handled by parent via onError callback; render empty placeholder
  if (isError) {
    return (
      <div className="flex items-center justify-center" style={{ width, height }}>
        <span className="text-gnosis-muted text-sm">Graph unavailable.</span>
      </div>
    );
  }

  return (
    <ForceGraph2D
      ref={fgRef}
      graphData={graphData}
      width={width}
      height={height}
      nodeId="id"
      nodeLabel="title"
      nodeColor={(n) => nodeColor(n as GraphNode)}
      nodeVal={(n)   => nodeVal(n as GraphNode)}
      onNodeClick={handleNodeClick}
      onNodeHover={(n) => setHovered(n ? (n as GraphNode & { id: string }).id : null)}
      nodeCanvasObject={(node, ctx, globalScale) => {
        const n      = node as GraphNode & { x: number; y: number; id: string };
        const label  = n.title ?? n.id;
        const size   = nodeVal(n);
        const color  = nodeColor(n);
        const isHov  = hovered === n.id;

        ctx.beginPath();
        ctx.arc(n.x, n.y, size, 0, 2 * Math.PI);
        ctx.fillStyle   = color;
        ctx.globalAlpha = isHov ? 1 : 0.85;
        ctx.fill();
        ctx.globalAlpha = 1;

        if (globalScale >= 1.5 || isHov) {
          const fontSize = Math.max(4, 12 / globalScale);
          ctx.font        = `${fontSize}px sans-serif`;
          ctx.textAlign   = 'center';
          ctx.textBaseline = 'middle';
          ctx.fillStyle   = '#fff';
          ctx.fillText(label, n.x, n.y + size + fontSize);
        }
      }}
      nodeCanvasObjectMode={() => 'after'}
      linkColor={() => 'rgba(156,163,175,0.4)'}
      linkWidth={1}
      backgroundColor="transparent"
    />
  );
}

export default GraphView2D;
