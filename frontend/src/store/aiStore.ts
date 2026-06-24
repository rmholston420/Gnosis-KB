/**
 * aiStore — Zustand slice for AI provider configuration and chat session.
 */
import { create } from 'zustand';
import { persist } from 'zustand/middleware';
import { immer } from 'zustand/middleware/immer';
import type { AiChatMessage, RagMode } from '../types';

export type LlmProvider = 'ollama' | 'groq' | 'openai' | 'openrouter';

interface AiState {
  /** Selected LLM provider. */
  provider:    LlmProvider;
  /** Current RAG query mode. */
  ragMode:     RagMode;
  /** Active chat session messages. */
  history:     AiChatMessage[];
  /** True while an SSE stream is active. */
  isStreaming: boolean;
  /** Last stream error, if any. */
  streamError: string | null;
  /** Persisted Ollama model selection. */
  ollamaModel: string;

  // ---- Actions ----
  setProvider:    (p: LlmProvider) => void;
  setRagMode:     (m: RagMode) => void;
  appendMessage:  (msg: AiChatMessage) => void;
  updateLastMsg:  (content: string, citations?: string[]) => void;
  setStreaming:   (v: boolean) => void;
  setStreamError: (e: string | null) => void;
  clearHistory:   () => void;
  setOllamaModel: (model: string) => void;
}

export const useAiStore = create<AiState>()(
  persist(
    immer<AiState>((set) => ({
      provider:    'ollama',
      ragMode:     'hybrid',
      history:     [],
      isStreaming: false,
      streamError: null,
      ollamaModel: 'qwen2.5:14b',

      setProvider:    (p) => set((s) => { s.provider    = p; }),
      setRagMode:     (m) => set((s) => { s.ragMode     = m; }),
      setStreaming:   (v) => set((s) => { s.isStreaming  = v; }),
      setStreamError: (e) => set((s) => { s.streamError = e; }),
      setOllamaModel: (model) => set((s) => { s.ollamaModel = model; }),

      appendMessage: (msg) => set((s) => {
        s.history.push(msg);
      }),

      updateLastMsg: (content, citations) => set((s) => {
        const last = s.history[s.history.length - 1];
        if (last?.role === 'assistant') {
          last.content    = content;
          last.citations  = citations;
        } else {
          s.history.push({ role: 'assistant', content, citations });
        }
      }),

      clearHistory: () => set((s) => {
        s.history     = [];
        s.isStreaming  = false;
        s.streamError = null;
      }),
    })),
    {
      name:    'gnosis-ai-store',
      // Only persist provider + model preferences, not the chat history
      partialize: (s) => ({ provider: s.provider, ragMode: s.ragMode, ollamaModel: s.ollamaModel }),
    },
  ),
);
