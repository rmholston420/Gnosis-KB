/**
 * api/ai.ts — typed API client for AI/LLM endpoints.
 *
 * All result types re-exported so both hooks/useAI.ts and components
 * can import them from a single canonical location.
 */
import type { LinkSuggestion, TagSuggestion, AiCritique } from '../types';

const BASE = (import.meta as unknown as { env: Record<string, string> }).env?.VITE_API_URL ?? '';

async function req<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(`${BASE}${path}`, {
    headers: { 'Content-Type': 'application/json' },
    ...init,
  });
  if (!res.ok) throw new Error(`AI API ${res.status}: ${path}`);
  return res.json() as Promise<T>;
}

export interface SummarizeResult   { summary:     string }
export interface CritiqueResult    { overall_feedback: string; critique: AiCritique }
export interface LinkSuggestResult { suggestions: LinkSuggestion[] }
export interface TagSuggestResult  { suggestions: TagSuggestion[] }
export interface ChatQueryResult   { answer: string; sources?: string[]; mode?: string }
export interface OrphanAuditResult { orphans: string[] }

// Re-export entity types so components don't need a separate import
export type { LinkSuggestion, TagSuggestion, AiCritique };

export const aiApi = {
  summarizeNote:  (id: string) =>
    req<SummarizeResult>(`/api/ai/summarize/${id}`, { method: 'POST' }),
  critiqueNote:   (id: string) =>
    req<CritiqueResult>(`/api/ai/critique/${id}`, { method: 'POST' }),
  suggestLinks:   (id: string) =>
    req<LinkSuggestResult>(`/api/ai/suggest-links/${id}`, { method: 'POST' }),
  suggestTags:    (id: string) =>
    req<TagSuggestResult>(`/api/ai/suggest-tags/${id}`, { method: 'POST' }),
  streamQuery: (
    query: string,
    onChunk?: (token: string) => void,
    onDone?:  () => void,
  ) => {
    const url  = `${BASE}/api/ai/query`;
    const ctrl = new AbortController();
    fetch(url, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ query }),
      signal: ctrl.signal,
    }).then(async res => {
      const reader  = res.body?.getReader();
      const decoder = new TextDecoder();
      if (!reader) { onDone?.(); return; }
      for (;;) {
        const { done, value } = await reader.read();
        if (done) break;
        onChunk?.(decoder.decode(value, { stream: true }));
      }
      onDone?.();
    }).catch(() => onDone?.());
    return () => ctrl.abort();
  },
};

export default aiApi;

// ── Standalone named exports used by hooks/useAI.ts ─────────────────────────

/** Non-streaming chat query — returns { answer, sources, mode }. */
export function chatQuery(
  params: { query: string; mode?: string },
): Promise<ChatQueryResult> {
  return req<ChatQueryResult>('/api/ai/query', {
    method: 'POST',
    body: JSON.stringify(params),
  });
}

/** Link suggestions (named export alias of aiApi.suggestLinks). */
export const suggestLinks       = aiApi.suggestLinks;
export const getLinkSuggestions = aiApi.suggestLinks;

/** Tag suggestions (named export alias of aiApi.suggestTags). */
export const suggestTags = aiApi.suggestTags;

/** Zettelkasten critique (named export alias of aiApi.critiqueNote). */
export function critiqueNote(noteId: string): Promise<CritiqueResult> {
  return aiApi.critiqueNote(noteId);
}

/** Orphan audit — returns notes with no incoming or outgoing links. */
export function orphanAudit(): Promise<OrphanAuditResult> {
  return req<OrphanAuditResult>('/api/ai/orphan-audit', { method: 'POST' });
}

/** Build the SSE URL for streaming chat. */
export function streamingChatUrl(
  params: { message: string; mode?: string; session_id?: string },
): string {
  const p = new URLSearchParams({
    message:    params.message,
    mode:       params.mode ?? 'hybrid',
    ...(params.session_id ? { session_id: params.session_id } : {}),
  });
  return `${BASE}/api/ai/stream?${p.toString()}`;
}
