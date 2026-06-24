/**
 * GraphPage — full-screen knowledge graph view.
 */
import React, { useState } from 'react';
import { GraphView2D } from '../components/graph/GraphView2D';
import { GraphControls } from '../components/graph/GraphControls';
import { NodeDetailOverlay } from '../components/graph/NodeDetailOverlay';
import type { GraphNode, GraphEntitySummary } from '../types';

export default function GraphPage() {
  const [selectedNode, setSelectedNode] = useState<GraphNode | null>(null);

  return (
    <div className="relative w-full h-full bg-gnosis-bg overflow-hidden">
      {/* Graph */}
      <GraphView2D
        onNodeClick={(node) => setSelectedNode(node)}
      />

      {/* Controls overlay */}
      <div className="absolute top-4 left-4 z-10">
        <GraphControls />
      </div>

      {/* Node detail panel */}
      {selectedNode && (
        <NodeDetailOverlay
          node={selectedNode}
          onClose={() => setSelectedNode(null)}
        />
      )}
    </div>
  );
}
