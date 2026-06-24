/**
 * AI API — typed wrappers around /api/v1/ai endpoints.
 * Streaming chat uses SSE — see useAI hook for EventSource integration.
 */
import client from './client';
import type { AiChatMessage, AiChatResponse, LinkSuggestion, TagSuggestion, AiCritique } from '../types';

export type RagMode = 'local' | 'global' | 'hybrid';

export interface ChatPayload {
  message: string;
  history?: AiChatMessage[];
  mode?: RagMode;
  session_id?: string;
}

/** RAG-powered chat over the vault (non-streaming). */
export async function chat(payload: ChatPayload): Promise<AiChatResponse> {
  const { data } = await client.post<AiChatResponse>('/api/v1/ai/chat', payload);
  return data;
}

/** AI summary of a note. */
export async function summarizeNote(noteId: string): Promise<{ summary: string }> {
  const { data } = await client.post<{ summary: string }>(`/api/v1/ai/summarize/${noteId}`);
  return data;
}

/** Suggest wikilinks for a note. */
export async function suggestLinks(noteId: string): Promise<LinkSuggestion[]> {
  const { data } = await client.post<LinkSuggestion[]>(`/api/v1/ai/suggest-links/${noteId}`);
  return data;
}

/** Suggest tags for a note. */
export async function suggestTags(noteId: string): Promise<TagSuggestion[]> {
  const { data } = await client.post<TagSuggestion[]>(`/api/v1/ai/suggest-tags/${noteId}`);
  return data;
}

/** Zettelkasten atomicity + connectivity critique. */
export async function critiqueNote(noteId: string): Promise<AiCritique> {
  const { data } = await client.post<AiCritique>(`/api/v1/ai/critique/${noteId}`);
  return data;
}

/** AI orphan audit — suggest connections for isolated notes. */
export async function orphanAudit(): Promise<Array<{ note_id: string; suggestions: LinkSuggestion[] }>> {
  const { data } = await client.get<Array<{ note_id: string; suggestions: LinkSuggestion[] }>>('/api/v1/ai/orphan-audit');
  return data;
}

/** Generate daily review from inbox notes. */
export async function dailyReview(): Promise<{ review: string }> {
  const { data } = await client.post<{ review: string }>('/api/v1/ai/daily-review');
  return data;
}

/**
 * Build an EventSource URL for SSE streaming chat.
 * Usage: new EventSource(streamingChatUrl({ message: '...' }))
 */
export function streamingChatUrl(payload: ChatPayload): string {
  const base = client.defaults.baseURL ?? '';
  const params = new URLSearchParams({
    message: payload.message,
    mode: payload.mode ?? 'hybrid',
    ...(payload.session_id ? { session_id: payload.session_id } : {}),
  });
  return `${base}/api/v1/ai/stream/chat?${params.toString()}`;
}
