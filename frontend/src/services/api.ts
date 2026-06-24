/**
 * services/api.ts — typed API client for every backend endpoint.
 * Consumed by hooks in src/hooks/* and modules in src/api/*.
 */
import type {
  Note, NoteCreateInput, NoteUpdateInput,
  SearchResult, SearchResponse,
  GraphData, LightRagGraphData, GraphEntity, GraphNode,
  AiChatMessage, AiChatResponse, AiAnalysisResult,
  VaultSyncStatus,
} from '../types';

const BASE = (import.meta as any).env?.VITE_API_BASE_URL ?? '/api';

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(`${BASE}${path}`, {
    headers: { 'Content-Type': 'application/json', ...init?.headers },
    ...init,
  });
  if (!res.ok) {
    const msg = await res.text().catch(() => res.statusText);
    throw new Error(`API ${res.status}: ${msg}`);
  }
  return res.json() as Promise<T>;
}

// Notes
export const getNotes = (params?: { page?: number; limit?: number; tag?: string; type?: string }) => {
  const q = new URLSearchParams();
  if (params?.page)  q.set('page',  String(params.page));
  if (params?.limit) q.set('limit', String(params.limit));
  if (params?.tag)   q.set('tag',   params.tag);
  if (params?.type)  q.set('type',  params.type);
  return request<{ notes: Note[]; total: number }>(`/notes${q.toString() ? `?${q}` : ''}`);
};
export const getNote    = (id: string)                    => request<Note>(`/notes/${id}`);
export const createNote = (data: NoteCreateInput)         => request<Note>('/notes', { method: 'POST', body: JSON.stringify(data) });
export const updateNote = (id: string, d: NoteUpdateInput)=> request<Note>(`/notes/${id}`, { method: 'PATCH', body: JSON.stringify(d) });
export const deleteNote = (id: string)                    => request<{ success: boolean }>(`/notes/${id}`, { method: 'DELETE' });

// Search
export const searchNotes    = (q: string, limit = 20) => request<SearchResponse>(`/search/keyword?q=${encodeURIComponent(q)}&limit=${limit}`);
export const semanticSearch = (q: string, limit = 20) => request<SearchResponse>(`/search/semantic?q=${encodeURIComponent(q)}&limit=${limit}`);
export const hybridSearch   = (q: string, limit = 20) => request<SearchResponse>(`/search/hybrid?q=${encodeURIComponent(q)}&limit=${limit}`);
export const getSimilarNotes= (id: string, limit = 6) => request<SearchResult[]>(`/notes/${id}/similar?limit=${limit}`);

// Graph
export const getFullGraph      = ()             => request<GraphData>('/graph');
export const getLightRagGraph  = ()             => request<LightRagGraphData>('/graph/lightrag');
export const getGraphEntities  = (type?: string)=> request<GraphEntity[]>(`/graph/entities${type ? `?type=${encodeURIComponent(type)}` : ''}`);
export const getGraphNode      = (id: string)   => request<GraphNode>(`/graph/nodes/${id}`);

// AI / Vault
export const triggerVaultSync     = ()                                         => request<VaultSyncStatus>('/vault/sync', { method: 'POST' });
export const triggerAiAnalysis    = (noteId: string)                           => request<AiAnalysisResult>(`/ai/analyze/${noteId}`, { method: 'POST' });
export const generateLinkedNotes  = (noteId: string)                           => request<Note[]>(`/ai/link-suggestions/${noteId}`, { method: 'POST' });
export const aiChat               = (messages: AiChatMessage[], ctx?: string)  => request<AiChatResponse>('/ai/chat', { method: 'POST', body: JSON.stringify({ messages, noteContext: ctx }) });
export const getAiHistory         = (sessionId: string)                        => request<AiChatMessage[]>(`/ai/history/${sessionId}`);

export default {
  getNotes, getNote, createNote, updateNote, deleteNote,
  searchNotes, semanticSearch, hybridSearch, getSimilarNotes,
  getFullGraph, getLightRagGraph, getGraphEntities, getGraphNode,
  triggerVaultSync, triggerAiAnalysis, generateLinkedNotes, aiChat, getAiHistory,
};
