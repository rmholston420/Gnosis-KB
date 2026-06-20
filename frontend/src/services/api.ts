/**
 * Gnosis API service layer.
 * All HTTP calls go through typed fetch wrappers.
 * Base URL: /api/v1 (proxied by Vite dev server to :8010 in dev)
 *
 * Vault scoping
 * -------------
 * When the user is browsing a shared vault, useVaultStore holds a non-null
 * activeVaultOwnerId.  request() reads this synchronously via Zustand’s
 * getState() selector (safe outside React components) and appends the header
 *   X-Vault-Owner-Id: <owner_id>
 * to every request.  The backend reads this header in a FastAPI dependency
 * (core/auth.py) and passes it to get_accessible_owner_ids() so note queries
 * are automatically scoped to the foreign vault when the header is present and
 * the caller has a valid grant, or fall back to their own vault otherwise.
 */

import { useVaultStore } from '../store/useVaultStore';

const BASE_URL = '/api/v1';

/** Headers injected into every request: auth token + optional vault scope. */
function buildCommonHeaders(extra: Record<string, string> = {}): Record<string, string> {
  const token = localStorage.getItem('gnosis_token') ?? '';
  const { activeVaultOwnerId } = useVaultStore.getState();

  const headers: Record<string, string> = {
    Authorization: `Bearer ${token}`,
    ...extra,
  };

  if (activeVaultOwnerId !== null) {
    headers['X-Vault-Owner-Id'] = String(activeVaultOwnerId);
  }

  return headers;
}

async function request<T>(
  method: string,
  path: string,
  body?: unknown,
  extraHeaders?: Record<string, string>
): Promise<T> {
  const res = await fetch(`${BASE_URL}${path}`, {
    method,
    headers: {
      'Content-Type': 'application/json',
      ...buildCommonHeaders(extraHeaders),
    },
    body: body !== undefined ? JSON.stringify(body) : undefined,
  });

  if (!res.ok) {
    const detail = await res.json().catch(() => ({ detail: res.statusText }));
    throw new Error(
      typeof detail.detail === 'string' ? detail.detail : JSON.stringify(detail)
    );
  }

  if (res.status === 204) return undefined as unknown as T;
  return res.json() as Promise<T>;
}

export const api = {
  // --- Notes ---
  listNotes: (params: Record<string, string | number>) =>
    request('GET', `/notes/?${new URLSearchParams(
      Object.entries(params)
        .filter(([, v]) => v !== undefined && v !== '')
        .map(([k, v]) => [k, String(v)])
    ).toString()}`),

  getNote: (id: string) => request('GET', `/notes/${id}`),

  createNote: (data: unknown) => request('POST', '/notes/', data),

  updateNote: (id: string, data: unknown) => request('PUT', `/notes/${id}`, data),

  deleteNote: (id: string) => request('DELETE', `/notes/${id}`),

  getDailyNote: () => request('GET', '/notes/daily'),

  getBacklinks: (id: string) => request('GET', `/notes/${id}/backlinks`),

  getOutlinks: (id: string) => request('GET', `/notes/${id}/outlinks`),

  getOrphanNotes: () => request('GET', '/notes/orphans'),

  /**
   * Wikilink title resolution — returns notes whose title contains `q`,
   * scoped to the caller’s accessible vaults.
   */
  searchNoteByTitle: (q: string) =>
    request('GET', `/notes/by-title?${new URLSearchParams({ q }).toString()}`),

  /** Fetch built-in note template gallery. */
  listTemplates: () => request('GET', '/notes/templates'),

  // --- Search ---
  search: (q: string, params: Record<string, string | number> = {}) =>
    request('GET', `/search/?q=${encodeURIComponent(q)}&${new URLSearchParams(
      Object.entries(params).map(([k, v]) => [k, String(v)])
    ).toString()}`),

  // --- Tags ---
  listTags: () => request('GET', '/tags/'),

  // --- Graph ---
  getFullGraph: () => request('GET', '/graph/'),

  getNeighborhood: (id: string) => request('GET', `/graph/neighborhood/${id}`),

  getPath: (fromId: string, toId: string) =>
    request('GET', `/graph/path/${fromId}/${toId}`),

  getClusters: () => request('GET', '/graph/clusters'),

  getGraphStats: () => request('GET', '/graph/stats'),

  /** Fetch LightRAG entity/relation graph for D3 visualisation. */
  getLightRagGraph: () => request('GET', '/graph/lightrag'),

  /** Fetch raw LightRAG entity list for the entities panel. */
  getGraphEntities: (limit = 100) =>
    request<{ entities: GraphEntitySummary[] }>('GET', `/graph/entities?limit=${limit}`),

  // --- AI ---
  chat: (message: string, mode = 'hybrid', sessionId?: string) =>
    request('POST', '/ai/chat', { message, mode, session_id: sessionId }),

  summarizeNote: (id: string) => request('POST', `/ai/summarize/${id}`),

  critiqueNote: (id: string) => request('POST', `/ai/critique/${id}`),

  suggestLinks: (id: string) => request('POST', `/ai/suggest-links/${id}`),

  /** Trigger on-demand LightRAG ingestion of a single note (backfill). */
  ingestNote: (id: string) => request('POST', `/ai/ingest-note/${id}`),

  // --- AI Providers ---
  getProviders: () => request('GET', '/ai/providers'),

  setModel: (model: string) => request('POST', '/ai/providers/model', { model }),

  // --- Vault Sync (Slice 15) ---

  /**
   * Trigger a background vault sync (non-streaming).
   * Returns { status: 'accepted', message, user_id } immediately.
   */
  triggerVaultSync: () =>
    request<{ status: string; message: string; user_id: number }>('POST', '/vault/sync'),

  /**
   * Poll the current sync state for the authenticated user.
   * Returns SyncStatusResponse: { state, elapsed, files_processed, files_total }
   */
  getVaultSyncStatus: () =>
    request<VaultSyncStatus>('GET', '/vault/sync/status'),

  /**
   * Open an SSE stream for vault sync progress.
   *
   * Returns a native EventSource that emits one line per file processed.
   * The last event will be `data: [done]` or `data: [error] <msg>`.
   *
   * Note: EventSource does not support custom headers, so the auth token is
   * passed as a query param. The backend vault router reads ?token= as a
   * fallback when the Authorization header is absent.
   */
  openVaultSyncStream: (): EventSource => {
    const token = localStorage.getItem('gnosis_token') ?? '';
    const url = `${BASE_URL}/vault/sync?stream=true&token=${encodeURIComponent(token)}`;
    return new EventSource(url);
  },

  // --- Ingest ---
  // FormData requests can’t use Content-Type: application/json, so they
  // build headers manually via buildCommonHeaders() (no Content-Type override).
  ingestFile: (file: File, folder = '70-sources') => {
    const form = new FormData();
    form.append('file', file);
    form.append('folder', folder);
    return fetch(`${BASE_URL}/ingest/file`, {
      method: 'POST',
      headers: buildCommonHeaders(),
      body: form,
    }).then(async (res) => {
      if (!res.ok) throw new Error((await res.json()).detail || res.statusText);
      return res.json();
    });
  },

  ingestUrl: (url: string, folder = '70-sources') => {
    const form = new FormData();
    form.append('url', url);
    form.append('folder', folder);
    return fetch(`${BASE_URL}/ingest/url`, {
      method: 'POST',
      headers: buildCommonHeaders(),
      body: form,
    }).then(async (res) => {
      if (!res.ok) throw new Error((await res.json()).detail || res.statusText);
      return res.json();
    });
  },
};

// --- Shared types used by api methods above --------------------------------

export interface VaultSyncStatus {
  state: 'idle' | 'running' | 'done' | 'error';
  started: number | null;
  elapsed: number | null;
  files_processed: number;
  files_total: number;
  last_error: string | null;
}

export interface GraphEntitySummary {
  id: string;
  label: string;
  description?: string;
  cluster?: number;
  source_note_ids?: string[];
}

export default api;
