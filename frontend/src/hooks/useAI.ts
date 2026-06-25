/**
 * useAI — hooks for AI chat, summarization, suggestions, and critiques.
 * Streaming chat uses EventSource (SSE).
 *
 * Import strategy: import the entire api/ai module as a namespace (*) so that
 * Vitest vi.mock() replacements of named exports are picked up at call-time
 * (live ESM binding) rather than being frozen at import-time. This is required
 * for mutation data to be visible on result.current.data after act() in tests.
 */
import { useState, useCallback, useRef } from 'react';
import { useMutation, useQuery } from '@tanstack/react-query';
import * as aiModule from '../api/ai';
import type { AiChatMessage, RagMode } from '../types';
import type { LinkSuggestion } from '../api/ai';

// ── Mutation-based chat (used by tests: useAIChat) ────────────────────────
export interface AIChatInput {
  query: string;
  mode?: RagMode;
}

/** Mutation hook wrapping chatQuery. Returns { answer, sources, mode }. */
export function useAIChat() {
  return useMutation({
    mutationFn: (input: AIChatInput) =>
      aiModule.chatQuery({ query: input.query, mode: input.mode ?? 'hybrid' }),
  });
}

// ── Streaming SSE chat session (internal use in AiSidebar) ───────────────
export function useAiChatStream(sessionId?: string) {
  const [messages, setMessages]  = useState<AiChatMessage[]>([]);
  const [streaming, setStreaming] = useState(false);
  const [error, setError]         = useState<string | null>(null);
  const [ragMode, setRagMode]     = useState<RagMode>('hybrid');
  const esRef = useRef<EventSource | null>(null);

  const sendMessage = useCallback((text: string) => {
    const userMsg: AiChatMessage = { role: 'user', content: text };
    setMessages((prev) => [...prev, userMsg]);
    setStreaming(true);
    setError(null);

    esRef.current?.close();

    let buffer = '';
    const assistantIdx = messages.length + 1;

    const url = aiModule.streamingChatUrl({ message: text, mode: ragMode, session_id: sessionId });
    const es  = new EventSource(url);
    esRef.current = es;

    es.onmessage = (ev) => {
      if (ev.data === '[DONE]') {
        es.close();
        setStreaming(false);
        return;
      }
      try {
        const chunk = JSON.parse(ev.data) as { token?: string; citations?: string[] };
        buffer += chunk.token ?? '';
        setMessages((prev) => {
          const next = [...prev];
          const existing = next[assistantIdx];
          if (existing) {
            next[assistantIdx] = { ...existing, content: buffer, citations: chunk.citations };
          } else {
            next.push({ role: 'assistant', content: buffer, citations: chunk.citations });
          }
          return next;
        });
      } catch {
        // non-JSON event; skip
      }
    };

    es.onerror = () => {
      es.close();
      setStreaming(false);
      setError('Stream interrupted. Please try again.');
    };
  }, [messages.length, ragMode, sessionId]);

  const clearHistory = useCallback(() => {
    esRef.current?.close();
    setMessages([]);
    setError(null);
  }, []);

  return { messages, streaming, error, ragMode, setRagMode, sendMessage, clearHistory };
}

// Keep the old name as an alias for any existing callers
export const useAiChat = useAiChatStream;

/** Summarize a note via AI. */
export function useNoteSummary(noteId: string | null) {
  return useMutation({
    mutationFn: () => aiModule.summarizeNote(noteId!),
  });
}

/**
 * Suggest wikilinks for a note.
 *
 * The useAI.test mock returns a raw LinkSuggestion[] from getLinkSuggestions,
 * while suggestLinks (used in AiSidebar) returns LinkSuggestResult { suggestions }.
 * Normalise both shapes: if the response is an array, return it directly;
 * if it has a .suggestions property, unwrap it.
 */
export function useLinkSuggestions(noteId: string | null) {
  return useQuery({
    queryKey: ['ai', 'suggest-links', noteId],
    queryFn: async (): Promise<LinkSuggestion[]> => {
      const res = await aiModule.suggestLinks(noteId!);
      if (Array.isArray(res)) return res as LinkSuggestion[];
      return (res as { suggestions: LinkSuggestion[] }).suggestions ?? [];
    },
    enabled:  !!noteId,
    staleTime: 300_000,
  });
}

/** Suggest tags for a note. */
export function useTagSuggestions(noteId: string | null) {
  return useQuery({
    queryKey: ['ai', 'suggest-tags', noteId],
    queryFn:  () => aiModule.suggestTags(noteId!),
    enabled:  !!noteId,
    staleTime: 300_000,
  });
}

/** Zettelkasten critique of a note. */
export function useCritiqueNote() {
  return useMutation({
    mutationFn: (noteId: string) => aiModule.critiqueNote(noteId),
  });
}

/** Old compat alias (keeps any existing callers working). */
export const useNoteCritique = useCritiqueNote;

/** Orphan audit (returns suggestions for all orphaned notes). */
export function useOrphanAudit() {
  return useQuery({
    queryKey: ['ai', 'orphan-audit'],
    queryFn:  () => aiModule.orphanAudit(),
    staleTime: 600_000,
  });
}
