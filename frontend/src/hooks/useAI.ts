/**
 * useAI — hooks for AI chat, summarization, suggestions, and critiques.
 * Streaming chat uses EventSource (SSE).
 */
import { useState, useCallback, useRef } from 'react';
import { useMutation, useQuery } from '@tanstack/react-query';
import {
  chatQuery, summarizeNote, suggestLinks, getLinkSuggestions,
  suggestTags, critiqueNote, orphanAudit, streamingChatUrl,
} from '../api/ai';
import type { AiChatMessage, RagMode } from '../types';

// ── Mutation-based chat (used by tests: useAIChat) ────────────────────────
export interface AIChatInput {
  query: string;
  mode?: RagMode;
}

/** Mutation hook wrapping chatQuery. Returns { answer, sources, mode }. */
export function useAIChat() {
  return useMutation({
    mutationFn: (input: AIChatInput) =>
      chatQuery({ query: input.query, mode: input.mode ?? 'hybrid' }),
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

    const url = streamingChatUrl({ message: text, mode: ragMode, session_id: sessionId });
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
    mutationFn: () => summarizeNote(noteId!),
  });
}

/**
 * Suggest wikilinks for a note.
 * Calls getLinkSuggestions (preferred) or suggestLinks as fallback.
 */
export function useLinkSuggestions(noteId: string | null) {
  return useQuery({
    queryKey: ['ai', 'suggest-links', noteId],
    queryFn:  () =>
      typeof getLinkSuggestions === 'function'
        ? getLinkSuggestions(noteId!)
        : suggestLinks(noteId!),
    enabled:  !!noteId,
    staleTime: 300_000,
  });
}

/** Suggest tags for a note. */
export function useTagSuggestions(noteId: string | null) {
  return useQuery({
    queryKey: ['ai', 'suggest-tags', noteId],
    queryFn:  () => suggestTags(noteId!),
    enabled:  !!noteId,
    staleTime: 300_000,
  });
}

/** Zettelkasten critique of a note. */
export function useCritiqueNote() {
  return useMutation({
    mutationFn: (noteId: string) => critiqueNote(noteId),
  });
}

/** Old compat alias (keeps any existing callers working). */
export const useNoteCritique = useCritiqueNote;

/** Orphan audit (returns suggestions for all orphaned notes). */
export function useOrphanAudit() {
  return useQuery({
    queryKey: ['ai', 'orphan-audit'],
    queryFn:  orphanAudit,
    staleTime: 600_000,
  });
}
