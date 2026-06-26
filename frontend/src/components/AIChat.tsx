/**
 * AIChat: Real-time streaming chat with the Gnosis knowledge graph.
 *
 * Uses fetch() + ReadableStream for SSE so we can send the Authorization
 * header — EventSource does not support custom headers.
 * Token is read from localStorage ('gnosis_token') to mirror api.ts.
 *
 * Meta event: the backend emits a single `{meta: {rag_source, mode}}`
 * event just before [DONE].  We capture it and display a colour-coded badge
 * beneath the assistant message.
 *
 * Fix: assistantIdx previously captured `messages.length + 1` from a stale
 * closure over the pre-setState `messages` array.  React batches state
 * updates, so after adding both the user message and the empty assistant
 * stub in two separate `setMessages` calls, the index was off-by-one in all
 * edge cases (first message, rapid sends).  We now use a `useRef` counter
 * that is incremented atomically alongside each pair of pushes and read
 * directly inside the streaming callbacks, so it is always correct regardless
 * of React's scheduler timing.
 */

import { useRef, useState } from 'react';
import { Send, Loader2, Bot, User, Zap, BookOpen, Cpu } from 'lucide-react';
import type { ChatMessage } from '../types';

const API_BASE = import.meta.env.VITE_API_BASE_URL ?? 'http://localhost:8000/api/v1';

type RagSource = 'lightrag' | 'vector' | 'hybrid' | 'naive';
type ChatMode  = 'hybrid' | 'lightrag' | 'vector' | 'naive';

/** Extend Record<string,unknown> so AIChatMessage.meta is satisfied. */
interface MetaPayload extends Record<string, unknown> {
  rag_source: RagSource;
  mode:       ChatMode;
}

const SOURCE_BADGE: Record<RagSource, { label: string; className: string }> = {
  lightrag: { label: 'LightRAG', className: 'bg-purple-500/20 text-purple-300 border-purple-500/30' },
  vector:   { label: 'Vector',   className: 'bg-blue-500/20   text-blue-300   border-blue-500/30'   },
  hybrid:   { label: 'Hybrid',   className: 'bg-teal-500/20   text-teal-300   border-teal-500/30'   },
  naive:    { label: 'Naive',    className: 'bg-gray-500/20   text-gray-300   border-gray-500/30'   },
};

interface AIChatMessage extends ChatMessage {
  meta?: MetaPayload;
}

export default function AIChat() {
  const [messages, setMessages] = useState<AIChatMessage[]>([]);
  const [input,    setInput]    = useState('');
  const [loading,  setLoading]  = useState(false);
  const [mode,     setMode]     = useState<ChatMode>('hybrid');
  const bottomRef     = useRef<HTMLDivElement>(null);
  const sessionRef    = useRef<string>(crypto.randomUUID());
  // Stable ref to the index of the in-progress assistant message.
  // Updated atomically inside the functional setState updater so streaming
  // callbacks never read a stale closure value.
  const assistantIdxRef = useRef<number>(-1);

  async function send() {
    const text = input.trim();
    if (!text || loading) return;

    const userMsg: AIChatMessage = { role: 'user', content: text };

    // Collapse both pushes into one functional updater so `prev` is always
    // the actual current array.  Capture the assistant slot index here where
    // it is guaranteed correct, then persist it in the ref.
    setMessages((prev) => {
      assistantIdxRef.current = prev.length + 1; // user at prev.length, assistant at +1
      return [...prev, userMsg, { role: 'assistant', content: '' }];
    });

    setInput('');
    setLoading(true);

    try {
      const token = localStorage.getItem('gnosis_token') ?? '';
      const res = await fetch(`${API_BASE}/ai/chat/stream`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          Authorization: `Bearer ${token}`,
        },
        body: JSON.stringify({ message: text, mode, session_id: sessionRef.current }),
      });

      if (!res.ok || !res.body) {
        throw new Error(`HTTP ${res.status}`);
      }

      const reader  = res.body.getReader();
      const decoder = new TextDecoder();
      let accumulated = '';
      let buf = '';

      // eslint-disable-next-line no-constant-condition
      while (true) {
        const { done, value } = await reader.read();
        if (done) break;

        buf += decoder.decode(value, { stream: true });

        const parts = buf.split('\n\n');
        buf = parts.pop() ?? '';

        for (const part of parts) {
          for (const line of part.split('\n')) {
            if (!line.startsWith('data: ')) continue;
            const payload = line.slice(6).trim();
            if (payload === '[DONE]') continue;
            try {
              const parsed = JSON.parse(payload) as
                | { token: string }
                | { meta: MetaPayload }
                | { error: string };

              // Read from ref — never from a stale closure.
              const idx = assistantIdxRef.current;

              if ('error' in parsed) {
                accumulated += `\n\n*Error: ${parsed.error}*`;
              } else if ('meta' in parsed) {
                setMessages((prev) =>
                  prev.map((m, i) =>
                    i === idx ? { ...m, meta: parsed.meta } : m
                  )
                );
              } else if ('token' in parsed) {
                accumulated += parsed.token;
                setMessages((prev) =>
                  prev.map((m, i) =>
                    i === idx ? { ...m, content: accumulated } : m
                  )
                );
                bottomRef.current?.scrollIntoView({ behavior: 'smooth' });
              }
            } catch {
              // ignore non-JSON lines
            }
          }
        }
      }
    } catch (err) {
      const msg = err instanceof Error ? err.message : 'Unknown error';
      const idx = assistantIdxRef.current;
      setMessages((prev) =>
        prev.map((m, i) =>
          i === idx
            ? { ...m, content: `*Failed to get response: ${msg}*` }
            : m
        )
      );
    } finally {
      setLoading(false);
      bottomRef.current?.scrollIntoView({ behavior: 'smooth' });
    }
  }

  return (
    <div className="flex h-full flex-col bg-bg-primary text-text-primary">

      {/* Mode selector */}
      <div className="flex items-center gap-2 border-b border-border-default px-4 py-2">
        <span className="text-xs text-text-muted">Mode:</span>
        {(['hybrid', 'lightrag', 'vector', 'naive'] as ChatMode[]).map((m) => (
          <button
            key={m}
            onClick={() => setMode(m)}
            className={`rounded px-2 py-0.5 text-xs transition-colors ${
              mode === m
                ? 'bg-accent-teal text-white'
                : 'text-text-muted hover:bg-bg-elevated'
            }`}
          >
            {m}
          </button>
        ))}
      </div>

      {/* Message list */}
      <div className="flex-1 overflow-y-auto px-4 py-4 space-y-4">
        {messages.length === 0 && (
          <div className="flex flex-col items-center justify-center h-full gap-3 text-text-muted">
            <Bot size={40} className="opacity-30" />
            <p className="text-sm">Ask anything about your knowledge base</p>
          </div>
        )}
        {messages.map((msg, i) => (
          <div key={i} className={`flex gap-3 ${ msg.role === 'user' ? 'justify-end' : 'justify-start' }`}>
            {msg.role === 'assistant' && (
              <div className="flex-shrink-0 w-7 h-7 rounded-full bg-accent-teal/20 flex items-center justify-center">
                <Cpu size={14} className="text-accent-teal" />
              </div>
            )}
            <div className={`max-w-[75%] ${ msg.role === 'user' ? 'order-first' : '' }`}>
              <div
                className={`rounded-lg px-3 py-2 text-sm leading-relaxed ${
                  msg.role === 'user'
                    ? 'bg-accent-teal text-white ml-auto'
                    : 'bg-bg-secondary text-text-primary'
                }`}
              >
                {msg.content || (
                  <span className="inline-flex gap-1">
                    <span className="animate-bounce" style={{ animationDelay: '0ms'   }}>&middot;</span>
                    <span className="animate-bounce" style={{ animationDelay: '150ms' }}>&middot;</span>
                    <span className="animate-bounce" style={{ animationDelay: '300ms' }}>&middot;</span>
                  </span>
                )}
              </div>
              {msg.role === 'assistant' && msg.meta && (() => {
                const badge = SOURCE_BADGE[msg.meta.rag_source];
                return badge ? (
                  <div className="mt-1 flex items-center gap-1.5">
                    <span className={`rounded border px-1.5 py-0.5 text-xs font-medium ${badge.className}`}>
                      {badge.label}
                    </span>
                    <span className="text-xs text-text-faint capitalize">{msg.meta.mode} mode</span>
                  </div>
                ) : null;
              })()}
            </div>
            {msg.role === 'user' && (
              <div className="flex-shrink-0 w-7 h-7 rounded-full bg-bg-tertiary flex items-center justify-center">
                <User size={14} className="text-text-muted" />
              </div>
            )}
          </div>
        ))}
        <div ref={bottomRef} />
      </div>

      {/* Input */}
      <div className="border-t border-border-default px-4 py-3">
        <div className="flex items-end gap-2">
          <textarea
            value={input}
            onChange={(e) => setInput(e.target.value)}
            onKeyDown={(e) => {
              if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); void send(); }
            }}
            placeholder="Ask your knowledge base\u2026"
            rows={1}
            className="flex-1 resize-none rounded-lg bg-bg-secondary px-3 py-2 text-sm focus:outline-none border border-border-default min-h-[36px] max-h-[120px]"
            style={{ height: 'auto' }}
          />
          <button
            onClick={() => void send()}
            disabled={loading || !input.trim()}
            className="flex-shrink-0 rounded-lg bg-accent-teal p-2 text-white hover:bg-accent-teal/80 disabled:opacity-50 transition-colors"
          >
            {loading ? <Loader2 size={16} className="animate-spin" /> : <Send size={16} />}
          </button>
        </div>
        <div className="mt-1.5 flex items-center gap-1 text-xs text-text-faint">
          <Zap size={10} />
          <span>Powered by LightRAG &middot; <BookOpen size={10} className="inline" /> references your vault</span>
        </div>
      </div>
    </div>
  );
}
