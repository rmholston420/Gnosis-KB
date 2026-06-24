/**
 * useGraph — hooks for fetching and interacting with the knowledge graph.
 */
import { useQuery } from '@tanstack/react-query';
import { useState, useMemo } from 'react';
import { getFullGraph, getNeighborhood, getGraphStats, getClusters } from '../api/graph';
import { toForceGraphData, filterToNeighborhood } from '../lib/graphUtils';
import type { GraphData, GraphStats } from '../types';

/** Fetch the full knowledge graph and convert it for react-force-graph. */
export function useFullGraph() {
  const query = useQuery<GraphData>({
    queryKey:  ['graph', 'full'],
    queryFn:   getFullGraph,
    staleTime: 60_000,
  });

  const forceData = useMemo(
    () => (query.data ? toForceGraphData(query.data) : { nodes: [], links: [] }),
    [query.data],
  );

  return { ...query, forceData };
}

/** Fetch a note's ego-graph (1-hop neighborhood). */
export function useNeighborhood(noteId: string | null, hops = 1) {
  return useQuery<GraphData>({
    queryKey: ['graph', 'neighborhood', noteId, hops],
    queryFn:  () => getNeighborhood(noteId!, hops),
    enabled:  !!noteId,
  });
}

/** Fetch graph statistics (density, avg degree, orphan count). */
export function useGraphStats() {
  return useQuery<GraphStats>({
    queryKey:  ['graph', 'stats'],
    queryFn:   getGraphStats,
    staleTime: 120_000,
  });
}

/** Fetch community clusters. */
export function useGraphClusters() {
  return useQuery<GraphData>({
    queryKey:  ['graph', 'clusters'],
    queryFn:   getClusters,
    staleTime: 120_000,
  });
}

/**
 * Combined hook for the GraphPage:
 * manages focus node, neighborhood filter toggle, and search highlight.
 */
export function useGraphView() {
  const { forceData, isLoading, isError } = useFullGraph();
  const [focusNodeId, setFocusNodeId]         = useState<string | null>(null);
  const [neighborhoodMode, setNeighborhoodMode] = useState(false);
  const [searchHighlight, setSearchHighlight]   = useState<Set<string>>(new Set());

  const displayData = useMemo(() => {
    if (neighborhoodMode && focusNodeId) {
      return filterToNeighborhood(forceData, focusNodeId, 2);
    }
    return forceData;
  }, [forceData, neighborhoodMode, focusNodeId]);

  return {
    displayData,
    focusNodeId, setFocusNodeId,
    neighborhoodMode, setNeighborhoodMode,
    searchHighlight,  setSearchHighlight,
    isLoading, isError,
  };
}
