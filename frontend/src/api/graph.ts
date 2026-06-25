/**
 * api/graph.ts — pure named-export pass-throughs for knowledge graph endpoints.
 *
 * Contract (enforced by useGraph.test.ts):
 *  - vi.mock('../../api/graph', () => ({ getFullGraph: vi.fn(), ... }))
 *    must fully replace this module — no runtime fallback to services/api.
 *  - Each export is a plain async function; useGraph.ts imports them by name.
 *
 * Do NOT import from services/api inside the function bodies — that would
 * bypass the vi.mock and call the real fetch layer during tests.
 * All imports from services/api are used ONLY at module level for type info
 * or default wire-up; Vitest replaces the entire module when vi.mock is used.
 */
import {
  getGraph as _getGraph,
  getFullGraph as _getFullGraph,
  getNeighborhood as _getNeighborhood,
  getGraphStats as _getGraphStats,
  getClusters as _getClusters,
  getGraphNode as _getGraphNode,
  getLightRagGraph as _getLightRagGraph,
  getGraphEntities as _getGraphEntities,
} from '../services/api';

export interface GraphEntitySummary {
  id: string;
  label: string;
  type?: string;
  description?: string;
}

// Plain named exports — vi.mock replaces these entirely in tests.
export function fetchGraph(...args: Parameters<typeof _getGraph>) {
  return _getGraph(...args);
}

export function getFullGraph(...args: Parameters<typeof _getFullGraph>) {
  return _getFullGraph(...args);
}

export function getNeighborhood(...args: Parameters<typeof _getNeighborhood>) {
  return _getNeighborhood(...args);
}

export function getGraphStats(...args: Parameters<typeof _getGraphStats>) {
  return _getGraphStats(...args);
}

export function getClusters(...args: Parameters<typeof _getClusters>) {
  return _getClusters(...args);
}

export function getGraphNode(...args: Parameters<typeof _getGraphNode>) {
  return _getGraphNode(...args);
}

export function getLightRagGraph(...args: Parameters<typeof _getLightRagGraph>) {
  return _getLightRagGraph(...args);
}

export function getGraphEntities(...args: Parameters<typeof _getGraphEntities>) {
  return _getGraphEntities(...args);
}
