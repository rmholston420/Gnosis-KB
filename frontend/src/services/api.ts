/**
 * Gnosis API service layer.
 * All HTTP calls go through typed fetch wrappers.
 * Base URL: /api/v1 (proxied by Vite dev server to :8010 in dev)
 */

const BASE_URL = '/api/v1';

async function request<T>(
  method: string,
  path: string,
  body?: unknown,
  headers?: Record<string, string>
): Promise<T> {
  const res = await fetch(`${BASE_URL}${path}`, {
    method,
    headers: {
      'Content-Type': 'application/json',
      ...headers,
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

  // --- AI ---
  chat: (message: string, mode = 'hybrid', sessionId?: string) =>
    request('POST', '/ai/chat', { message, mode, session_id: sessionId }),

  summarizeNote: (id: string) => request('POST', `/ai/summarize/${id}`),

  critiqueNote: (id: string) => request('POST', `/ai/critique/${id}`),

  suggestLinks: (id: string) => request('POST', `/ai/suggest-links/${id}`),

  // --- Ingest ---
  ingestFile: (file: File, folder = '70-sources') => {
    const form = new FormData();
    form.append('file', file);
    form.append('folder', folder);
    return fetch(`${BASE_URL}/ingest/file`, { method: 'POST', body: form }).then(
      async (res) => {
        if (!res.ok) throw new Error((await res.json()).detail || res.statusText);
        return res.json();
      }
    );
  },

  ingestUrl: (url: string, folder = '70-sources') => {
    const form = new FormData();
    form.append('url', url);
    form.append('folder', folder);
    return fetch(`${BASE_URL}/ingest/url`, { method: 'POST', body: form }).then(
      async (res) => {
        if (!res.ok) throw new Error((await res.json()).detail || res.statusText);
        return res.json();
      }
    );
  },
};

export default api;
