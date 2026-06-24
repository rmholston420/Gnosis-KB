/**
 * graphStore — Zustand slice for knowledge graph view state.
 * Manages filter settings, selected node, and cluster visibility.
 */
import { create } from 'zustand';
import { immer } from 'zustand/middleware/immer';

export type NoteType = 'permanent' | 'fleeting' | 'project' | 'area' | 'resource' | 'journal' | 'moc' | 'literature';

interface GraphState {
  /** Note ID of the currently selected / focused node, or null. */
  selectedNodeId:    string | null;
  /** Note types to show (empty set = show all). */
  visibleTypes:      Set<NoteType>;
  /** True = only show the focused node + its neighbors. */
  neighborhoodMode:  boolean;
  /** True = color nodes by community cluster instead of note type. */
  clusterMode:       boolean;
  /** Search query for highlighting matching nodes in the graph. */
  highlightQuery:    string;
  /** Show node labels at all zoom levels. */
  showLabels:        boolean;

  // ---- Actions ----
  selectNode:          (id: string | null) => void;
  toggleType:          (type: NoteType) => void;
  setAllTypes:         (types: NoteType[]) => void;
  toggleNeighborhood:  () => void;
  toggleClusterMode:   () => void;
  setHighlightQuery:   (q: string) => void;
  toggleLabels:        () => void;
  reset:               () => void;
}

export const useGraphStore = create<GraphState>()(immer((set) => ({
  selectedNodeId:   null,
  visibleTypes:     new Set<NoteType>(),
  neighborhoodMode: false,
  clusterMode:      false,
  highlightQuery:   '',
  showLabels:       true,

  selectNode: (id) => set((s) => { s.selectedNodeId = id; }),

  toggleType: (type) => set((s) => {
    if (s.visibleTypes.has(type)) s.visibleTypes.delete(type);
    else                          s.visibleTypes.add(type);
  }),

  setAllTypes: (types) => set((s) => {
    s.visibleTypes = new Set(types);
  }),

  toggleNeighborhood: () => set((s) => { s.neighborhoodMode = !s.neighborhoodMode; }),
  toggleClusterMode:  () => set((s) => { s.clusterMode      = !s.clusterMode;      }),
  setHighlightQuery:  (q) => set((s) => { s.highlightQuery   = q;                  }),
  toggleLabels:       () => set((s) => { s.showLabels        = !s.showLabels;       }),

  reset: () => set((s) => {
    s.selectedNodeId   = null;
    s.visibleTypes     = new Set();
    s.neighborhoodMode = false;
    s.clusterMode      = false;
    s.highlightQuery   = '';
    s.showLabels       = true;
  }),
})));
