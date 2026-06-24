import React from 'react';
import { useFullGraph } from '../hooks/useGraph';
import { GraphView2D } from '../components/graph/GraphView2D';
import { GraphControls } from '../components/graph/GraphControls';
import { NodeDetailOverlay } from '../components/graph/NodeDetailOverlay';
import type { GraphNode } from '../types';

export default function GraphPage() {
  const [selectedNode, setSelectedNode] = React.useState<GraphNode | null>(null);

  // Drive loading/error states from the actual data fetch so tests
  // (and the UI) reflect real async states rather than a setTimeout flag.
  const { isLoading, isError } = useFullGraph();

  return (
    <div className="relative w-full h-full bg-gnosis-bg overflow-hidden">
      {isLoading && (
        <div className="graph-page--loading" aria-label="Loading graph">
          Loading graph
        </div>
      )}

      {isError && (
        <div className="graph-page--error" role="alert">
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
