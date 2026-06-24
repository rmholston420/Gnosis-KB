/**
 * hooks/useAI.ts — TanStack Query hooks for AI features plus streaming chat mutation.
 */
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
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

export function useNoteSummary(noteId?: string | null) {
  return useQuery<SummarizeResult>({
    queryKey: ['ai', 'summary', noteId],
    queryFn: () => api.summarizeNote(noteId!) as Promise<SummarizeResult>,
    enabled: Boolean(noteId),
  });
}

export function useNoteCritique(noteId?: string | null) {
  return useQuery<CritiqueResult>({
    queryKey: ['ai', 'critique', noteId],
    queryFn: () => api.critiqueNote(noteId!) as Promise<CritiqueResult>,
    enabled: Boolean(noteId),
  });
}

export const useCritiqueNote = useNoteCritique;

export function useLinkSuggestions(noteId?: string | null) {
  return useQuery<LinkSuggestResult>({
    queryKey: ['ai', 'link-suggestions', noteId],
    queryFn: async () => {
      const result = await api.suggestLinks(noteId!);
      return Array.isArray(result) ? ({ suggestions: result } as LinkSuggestResult) : (result as LinkSuggestResult);
    },
    enabled: Boolean(noteId),
  });
}

export function useTagSuggestions(noteId?: string | null) {
  return useQuery<TagSuggestResult>({
    queryKey: ['ai', 'tag-suggestions', noteId],
    queryFn: async () => {
      const result = await api.suggestTags(noteId!);
      return Array.isArray(result) ? ({ suggestions: result } as TagSuggestResult) : (result as TagSuggestResult);
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
