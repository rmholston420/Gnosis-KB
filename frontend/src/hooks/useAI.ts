/**
 * hooks/useAI.ts — TanStack Query + Mutation hooks for AI features.
 *
 * All hooks expose the raw result envelopes so callers can decide how to
 * unwrap them (e.g. result?.suggestions, result?.summary).
 * The AiSidebar component does the unwrapping at render time.
 */
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { aiApi } from '../api/ai';
import type {
  SummarizeResult,
  CritiqueResult,
  LinkSuggestResult,
  TagSuggestResult,
} from '../api/ai';
import type { ChatMessage, ChatSource } from '../types';

// ── Note Summary (mutation — user triggers on demand) ────────────────────────

export function useNoteSummary(noteId?: string | null) {
  return useMutation<SummarizeResult, Error, string | undefined>({
    mutationFn: (id) => aiApi.summarizeNote((id ?? noteId)!),
  });
}

// ── Note Critique ─────────────────────────────────────────────────────────────

export function useNoteCritique(noteId?: string | null) {
  return useMutation<CritiqueResult, Error, string | undefined>({
    mutationFn: (id) => aiApi.critiqueNote((id ?? noteId)!),
  });
}

/** Alias kept for backward-compat with older test imports */
export const useCritiqueNote = useNoteCritique;

// ── Link Suggestions ──────────────────────────────────────────────────────────

/**
 * Returns the raw { suggestions: LinkSuggestion[] } envelope.
 * Callers should access data?.suggestions to get the array.
 */
export function useLinkSuggestions(noteId?: string | null) {
  return useQuery({
    queryKey: ['ai', 'link-suggestions', noteId],
    queryFn:  (): Promise<LinkSuggestResult> => aiApi.suggestLinks(noteId!),
    enabled:  Boolean(noteId),
  });
}

// ── Tag Suggestions ───────────────────────────────────────────────────────────

/**
 * Returns the raw { suggestions: TagSuggestion[] } envelope.
 * Callers should access data?.suggestions to get the array.
 */
export function useTagSuggestions(noteId?: string | null) {
  return useQuery({
    queryKey: ['ai', 'tag-suggestions', noteId],
    queryFn:  (): Promise<TagSuggestResult> => aiApi.suggestTags(noteId!),
    enabled:  Boolean(noteId),
  });
}

// ── AI Chat ───────────────────────────────────────────────────────────────────

export interface AiChatState {
  messages:    ChatMessage[];
  sources:     ChatSource[];
  isStreaming:  boolean;
  streamText:   string;
}

export function useAIChat() {
  const qc = useQueryClient();
  const send = useMutation<void, Error, string>({
    mutationFn: async (query: string) => {
      void qc;
      return new Promise<void>((resolve) => {
        aiApi.streamQuery(query, undefined, resolve);
      });
    },
  });
  return send;
}

export type { SummarizeResult, CritiqueResult, LinkSuggestResult, TagSuggestResult };
