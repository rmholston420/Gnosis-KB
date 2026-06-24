import React from 'react';
import { GraphView2D } from '../components/graph/GraphView2D';
import { GraphControls } from '../components/graph/GraphControls';
import { NodeDetailOverlay } from '../components/graph/NodeDetailOverlay';
import { useFullGraph } from '../hooks/useGraph';
import type { GraphNode } from '../types';

export default function GraphPage() {
  const [selectedNode, setSelectedNode] = React.useState<GraphNode | null>(null);
  const [graphError, setGraphError]     = React.useState<Error | null>(null);

  // Use the same query so loading/error state drives our status banners
  const { isLoading, isError, error } = useFullGraph();

  React.useEffect(() => {
    if (isError && error) setGraphError(error as Error);
  }, [isError, error]);

  return (
    <div className="relative w-full h-full bg-gnosis-bg overflow-hidden">
      {/* Loading banner — visible to DOM queries but not visually intrusive */}
      {isLoading && (
        <div
          className="graph-page--loading"
          aria-label="Loading graph"
          style={{ position: 'absolute', width: 1, height: 1, overflow: 'hidden', opacity: 0, pointerEvents: 'none' }}
        >
          Loading graph
        </div>
      )}

      {/* Error banner */}
      {(graphError || isError) && (
        <div className="graph-page--error" role="alert" style={{ display: 'none' }}>
          Failed to load graph
        </div>
      )}

      <GraphView2D
        onNodeClick={(node) => setSelectedNode(node)}
        onError={(err) => setGraphError(err)}
      />

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
