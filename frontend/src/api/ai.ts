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
export interface CritiqueResult    { critique:    AiCritique }
export interface LinkSuggestResult { suggestions: LinkSuggestion[] }
export interface TagSuggestResult  { suggestions: TagSuggestion[] }

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
      while (true) {
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

// ── Standalone named exports used by LinkSuggestions.tsx ────────────────────
export const suggestLinks = aiApi.suggestLinks;
