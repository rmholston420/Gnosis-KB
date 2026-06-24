/**
 * hooks/useAI.ts — TanStack Query hooks for AI features plus streaming chat mutation.
 *
 * Design contract (tests rely on this):
 *  useLinkSuggestions  → useQuery  (auto-fetches, no manual trigger)
 *  useTagSuggestions   → useQuery  (auto-fetches)
 *  useNoteSummary      → useMutation (manual trigger via mutate())
 *  useNoteCritique     → useMutation (manual trigger via mutate())
 *
 * All AI calls go through aiApi (api/ai.ts) so tests can spy on
 * that module's methods directly.
 */
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { aiApi } from '../api/ai';
import api from '../services/api';
import type { ChatMessage, ChatSource } from '../types';

export interface SummarizeResult {
  summary: string;
  keywords?: string[];
}

export interface CritiqueResult {
  critique: string;
  suggestions?: unknown[];
}

export interface LinkSuggestResult {
  suggestions: unknown[];
}

export interface TagSuggestResult {
  suggestions: unknown[];
}

/**
 * useNoteSummary — mutation so the user can trigger it on demand.
 * Returns { mutate, data, isPending } — same shape as useMutation.
 */
export function useNoteSummary(noteId?: string | null) {
  return useMutation<SummarizeResult, Error, undefined>({
    mutationFn: () => aiApi.summarizeNote(noteId!) as Promise<SummarizeResult>,
  });
}

/**
 * useNoteCritique / useCritiqueNote — mutation, on-demand.
 */
export function useNoteCritique(noteId?: string | null) {
  return useMutation<CritiqueResult, Error, undefined>({
    mutationFn: () => aiApi.critiqueNote(noteId!) as Promise<CritiqueResult>,
  });
}

export const useCritiqueNote = useNoteCritique;

/**
 * useLinkSuggestions — auto-fetching query via aiApi so tests can spy.
 */
export function useLinkSuggestions(noteId?: string | null) {
  return useQuery<LinkSuggestResult>({
    queryKey: ['ai', 'link-suggestions', noteId],
    queryFn: async () => {
      const result = await aiApi.suggestLinks(noteId!);
      return Array.isArray(result)
        ? ({ suggestions: result } as LinkSuggestResult)
        : (result as LinkSuggestResult);
    },
    enabled: Boolean(noteId),
  });
}

/**
 * useTagSuggestions — auto-fetching query via aiApi.
 */
export function useTagSuggestions(noteId?: string | null) {
  return useQuery<TagSuggestResult>({
    queryKey: ['ai', 'tag-suggestions', noteId],
    queryFn: async () => {
      const result = await aiApi.suggestTags(noteId!);
      return Array.isArray(result)
        ? ({ suggestions: result } as TagSuggestResult)
        : (result as TagSuggestResult);
    },
    enabled: Boolean(noteId),
  });
}

export interface AiChatState {
  messages: ChatMessage[];
  sources: ChatSource[];
  isStreaming: boolean;
  streamText: string;
}

export function useAIChat() {
  const qc = useQueryClient();
  return useMutation<void, Error, string>({
    mutationFn: async (query: string) => {
      void qc;
      return new Promise<void>((resolve) => {
        api.streamQuery(query, undefined, resolve);
      });
    },
  });
}

export type { ChatMessage, ChatSource };
