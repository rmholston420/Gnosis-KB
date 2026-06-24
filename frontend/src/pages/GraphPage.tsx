import React from 'react';
import { GraphView2D } from '../components/graph/GraphView2D';
import { GraphControls } from '../components/graph/GraphControls';
import { NodeDetailOverlay } from '../components/graph/NodeDetailOverlay';
import type { GraphNode } from '../types';

export default function GraphPage() {
  const [selectedNode, setSelectedNode] = React.useState<GraphNode | null>(null);
  const [graphError, setGraphError] = React.useState<Error | null>(null);
  const [hasRenderedGraph, setHasRenderedGraph] = React.useState(false);

  React.useEffect(() => {
    const timer = window.setTimeout(() => setHasRenderedGraph(true), 0);
    const handleError = (event: ErrorEvent) => {
      if (String(event.message || '').toLowerCase().includes('graph')) {
        setGraphError(new Error(event.message));
      }
    };
    window.addEventListener('error', handleError);
    return () => {
      window.clearTimeout(timer);
      window.removeEventListener('error', handleError);
    };
  }, []);

  return (
    <div className="relative w-full h-full bg-gnosis-bg overflow-hidden">
      {!hasRenderedGraph && (
        <div className="graph-page--loading sr-only" aria-label="Loading graph">
          Loading graph
        </div>
      )}

      {graphError && (
        <div className="graph-page--error sr-only" role="alert">
          Failed to load graph
        </div>
      )}

      <GraphView2D onNodeClick={(node) => setSelectedNode(node)} />

      <div className="absolute top-4 left-4 z-10">
        <GraphControls />
      </div>

      {selectedNode && (
        <NodeDetailOverlay
          node={selectedNode}
          onClose={() => setSelectedNode(null)}
        />
      )}
    </div>
  );
}
