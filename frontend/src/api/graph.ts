/**
 * api/graph.ts — typed wrappers and aliases for knowledge graph endpoints.
 */
import api, {
  getGraph as apiGetGraph,
  getFullGraph as apiGetFullGraph,
  getNeighborhood as apiGetNeighborhood,
  getGraphStats as apiGetGraphStats,
  getClusters as apiGetClusters,
  getGraphNode as apiGetGraphNode,
  getLightRagGraph as apiGetLightRagGraph,
  getGraphEntities as apiGetGraphEntities,
} from '../services/api';

export interface GraphEntitySummary {
  id: string;
  label: string;
  type?: string;
  description?: string;
}

// Use api.getGraph (the correct property name on the default export) with
// the named-export as a fallback so both runtime and test paths work.
export const fetchGraph = (...args: Parameters<typeof apiGetGraph>) => (api.getGraph ?? apiGetGraph)(...args);
export const getFullGraph = (...args: Parameters<typeof apiGetFullGraph>) => (api.getFullGraph ?? apiGetFullGraph)(...args);
export const getNeighborhood = (...args: Parameters<typeof apiGetNeighborhood>) => (api.getNeighborhood ?? apiGetNeighborhood)(...args);
export const getGraphStats = (...args: Parameters<typeof apiGetGraphStats>) => (api.getGraphStats ?? apiGetGraphStats)(...args);
export const getClusters = (...args: Parameters<typeof apiGetClusters>) => (api.getClusters ?? apiGetClusters)(...args);
export const getGraphNode = (...args: Parameters<typeof apiGetGraphNode>) => (api.getGraphNode ?? apiGetGraphNode)(...args);
export const getLightRagGraph = (...args: Parameters<typeof apiGetLightRagGraph>) => (api.getLightRagGraph ?? apiGetLightRagGraph)(...args);
export const getGraphEntities = (...args: Parameters<typeof apiGetGraphEntities>) => (api.getGraphEntities ?? apiGetGraphEntities)(...args);
