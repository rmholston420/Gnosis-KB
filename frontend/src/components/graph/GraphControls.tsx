/**
 * GraphControls — toolbar for the graph view.
 * Handles zoom, type filter, neighborhood mode, cluster mode, and search.
 */
import React from 'react';
import {
  ZoomIn, ZoomOut, Maximize2, LayoutGrid, GitBranch,
  Filter, Tag, Search, Eye, EyeOff,
} from 'lucide-react';
import { useGraphStore, type NoteType } from '../../store/graphStore';

const ALL_TYPES: NoteType[] = [
  'permanent', 'fleeting', 'project', 'area',
  'resource', 'journal', 'moc', 'literature',
];

const TYPE_COLORS: Record<NoteType, string> = {
  permanent:  '#3b82f6',
  fleeting:   '#94a3b8',
  project:    '#f59e0b',
  area:       '#10b981',
  resource:   '#8b5cf6',
  journal:    '#ec4899',
  moc:        '#ef4444',
  literature: '#f97316',
};

interface GraphControlsProps {
  onZoomIn?:       () => void;
  onZoomOut?:      () => void;
  onZoomToFit?:    () => void;
  onCenterGraph?:  () => void;
}

/**
 * Renders a floating control bar over the graph canvas.
 */
export function GraphControls({
  onZoomIn, onZoomOut, onZoomToFit, onCenterGraph,
}: GraphControlsProps) {
  const {
    visibleTypes, toggleType, setAllTypes,
    neighborhoodMode, toggleNeighborhood,
    clusterMode,      toggleClusterMode,
    highlightQuery,   setHighlightQuery,
    showLabels,       toggleLabels,
  } = useGraphStore();

  const allVisible   = visibleTypes.size === 0;
  const toggleAll    = () => setAllTypes(allVisible ? ALL_TYPES : []);

  return (
    <div className="absolute top-3 left-3 z-10 flex flex-col gap-2" aria-label="Graph controls">
      {/* Zoom controls */}
      <div className="flex flex-col gap-1 bg-gnosis-surface border border-gnosis-border rounded-md p-1 shadow-lg">
        <button onClick={onZoomIn}     title="Zoom in"      className="graph-ctrl-btn"><ZoomIn     size={14} /></button>
        <button onClick={onZoomOut}    title="Zoom out"     className="graph-ctrl-btn"><ZoomOut    size={14} /></button>
        <button onClick={onZoomToFit}  title="Fit to view"  className="graph-ctrl-btn"><Maximize2  size={14} /></button>
        <button onClick={onCenterGraph} title="Center graph" className="graph-ctrl-btn"><LayoutGrid size={14} /></button>
      </div>

      {/* View mode toggles */}
      <div className="flex flex-col gap-1 bg-gnosis-surface border border-gnosis-border rounded-md p-1 shadow-lg">
        <button
          onClick={toggleNeighborhood}
          title="Neighborhood mode"
          className={`graph-ctrl-btn ${neighborhoodMode ? 'text-gnosis-accent' : ''}`}
        >
          <GitBranch size={14} />
        </button>
        <button
          onClick={toggleClusterMode}
          title="Cluster color mode"
          className={`graph-ctrl-btn ${clusterMode ? 'text-gnosis-accent' : ''}`}
        >
          <Filter size={14} />
        </button>
        <button
          onClick={toggleLabels}
          title={showLabels ? 'Hide labels' : 'Show labels'}
          className="graph-ctrl-btn"
        >
          {showLabels ? <Eye size={14} /> : <EyeOff size={14} />}
        </button>
      </div>

      {/* Type filter */}
      <div className="bg-gnosis-surface border border-gnosis-border rounded-md p-2 shadow-lg">
        <div className="flex items-center gap-1 mb-1">
          <Tag size={11} className="text-gnosis-muted" />
          <span className="text-xs text-gnosis-muted">Filter</span>
          <button onClick={toggleAll} className="ml-auto text-xs text-gnosis-muted hover:text-gnosis-fg">
            {allVisible ? 'none' : 'all'}
          </button>
        </div>
        <div className="flex flex-col gap-0.5">
          {ALL_TYPES.map((t) => {
            const active = allVisible || visibleTypes.has(t);
            return (
              <button
                key={t}
                onClick={() => toggleType(t)}
                className={`flex items-center gap-1.5 text-xs px-1 py-0.5 rounded transition-opacity ${
                  active ? 'opacity-100' : 'opacity-30'
                }`}
              >
                <span
                  className="w-2 h-2 rounded-full flex-shrink-0"
                  style={{ background: TYPE_COLORS[t] }}
                />
                {t}
              </button>
            );
          })}
        </div>
      </div>

      {/* Node search highlight */}
      <div className="bg-gnosis-surface border border-gnosis-border rounded-md p-1.5 shadow-lg flex items-center gap-1">
        <Search size={12} className="text-gnosis-muted flex-shrink-0" />
        <input
          type="text"
          placeholder="Highlight\u2026"
          value={highlightQuery}
          onChange={(e) => setHighlightQuery(e.target.value)}
          className="bg-transparent text-xs text-gnosis-fg placeholder-gnosis-muted outline-none w-24"
          aria-label="Highlight nodes matching query"
        />
      </div>
    </div>
  );
}
