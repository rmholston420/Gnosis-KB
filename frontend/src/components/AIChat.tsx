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
 */

import { useRef, useState } from 'react';
import { Send, Loader2, Bot, User, Zap, BookOpen, Cpu } from 'lucide-react';
import type { ChatMessage } from '../types';

const API_BASE = import.meta.env.VITE_API_BASE_URL ?? 'http://localhost:8000/api/v1';

type RagSource = 'lightrag' | 'vector' | 'hybrid' | 'naive';
type ChatMode  = 'hybrid' | 'lightrag' | 'vector' | 'naive';

interface MetaPayload {
  rag_source: RagSource;
  mode: ChatMode;
  [key: string]: unknown;
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
  const bottomRef  = useRef<HTMLDivElement>(null);
  const sessionRef = useRef<string>(crypto.randomUUID());

  async function send() {
    const text = input.trim();
    if (!text || loading) return;

    const userMsg: AIChatMessage = { role: 'user', content: text };
    setMessages((prev) => [...prev, userMsg]);
    setInput('');
    setLoading(true);

    // Append a placeholder assistant message we'll stream into
    const assistantIdx = messages.length + 1;
    setMessages((prev) => [...prev, { role: 'assistant', content: '' }]);

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
        const lines = buf.split('\n');
        buf = lines.pop() ?? '';

        for (const line of lines) {
          if (!line.startsWith('data: ')) continue;
          const raw = line.slice(6).trim();
          if (raw === '[DONE]') continue;

          try {
            const parsed = JSON.parse(raw) as Record<string, unknown>;

            // Meta event
            if (parsed.meta) {
              setMessages((prev) => {
                const copy = [...prev];
                const last = copy[copy.length - 1];
                if (last?.role === 'assistant') {
                  copy[copy.length - 1] = { ...last, meta: parsed.meta as MetaPayload };
                }
                return copy;
              });
              continue;
            }

            // Text delta
            const delta = (parsed.choices as Array<{ delta?: { content?: string } }>)?.[0]?.delta?.content ?? '';
            if (!delta) continue;
            accumulated += delta;
            const snap = accumulated;
            setMessages((prev) => {
              const copy = [...prev];
              copy[assistantIdx] = { role: 'assistant', content: snap };
              return copy;
            });
          } catch {
            // ignore malformed JSON lines
          }
        }
      }
    } catch (err) {
      setMessages((prev) => {
        const copy = [...prev];
        copy[assistantIdx] = {
          role: 'assistant',
          content: `Error: ${err instanceof Error ? err.message : 'Unknown error'}`,
        };
        return copy;
      });
    } finally {
      setLoading(false);
      requestAnimationFrame(() => bottomRef.current?.scrollIntoView({ behavior: 'smooth' }));
    }
  }

  const MODE_OPTIONS: { value: ChatMode; label: string; icon: React.ReactNode }[] = [
    { value: 'hybrid',   label: 'Hybrid',   icon: <Zap      size={12} /> },
    { value: 'lightrag', label: 'LightRAG', icon: <Cpu      size={12} /> },
    { value: 'vector',   label: 'Vector',   icon: <BookOpen size={12} /> },
    { value: 'naive',    label: 'Naive',    icon: <Bot      size={12} /> },
  ];

  return (
    <div className="flex flex-col h-full bg-gnosis-bg">
      {/* Mode selector */}
      <div className="flex-shrink-0 flex gap-1 px-3 pt-3 pb-2">
        {MODE_OPTIONS.map((opt) => (
          <button
            key={opt.value}
            onClick={() => setMode(opt.value)}
            className={`flex items-center gap-1 px-2 py-1 rounded text-xs transition-colors ${
              mode === opt.value
                ? 'bg-gnosis-accent/20 text-gnosis-accent border border-gnosis-accent/30'
                : 'text-gnosis-muted hover:bg-gnosis-hover'
            }`}
          >
            {opt.icon}{opt.label}
          </button>
        ))}
      </div>

      {/* Message list */}
      <div className="flex-1 overflow-y-auto px-3 space-y-3 pb-3">
        {messages.length === 0 && (
          <div className="flex flex-col items-center justify-center h-full text-gnosis-muted gap-2 py-8">
            <Bot size={28} />
            <p className="text-sm">Ask anything about your vault…</p>
          </div>
        )}
        {messages.map((msg, i) => (
          <div key={i} className={`flex gap-2 ${ msg.role === 'user' ? 'justify-end' : 'justify-start' }`}>
            {msg.role === 'assistant' && (
              <div className="w-6 h-6 rounded-full bg-gnosis-accent/20 flex items-center justify-center flex-shrink-0 mt-0.5">
                <Bot size={12} className="text-gnosis-accent" />
              </div>
            )}
            <div className={`max-w-[85%] ${ msg.role === 'user' ? 'order-first' : '' }`}>
              <div className={`rounded-xl px-3 py-2 text-sm leading-relaxed ${
                msg.role === 'user'
                  ? 'bg-gnosis-accent/20 text-gnosis-fg ml-auto'
                  : 'bg-gnosis-surface text-gnosis-fg'
              }`}>
                {msg.content || (loading && msg.role === 'assistant' ? (
                  <Loader2 size={14} className="animate-spin text-gnosis-muted" />
                ) : null)}
              </div>
              {msg.role === 'assistant' && msg.meta && (
                <div className="mt-1 flex gap-1">
                  <span className={`text-xs px-1.5 py-0.5 rounded border ${
                    SOURCE_BADGE[msg.meta.rag_source]?.className ?? 'bg-gray-500/20 text-gray-300 border-gray-500/30'
                  }`}>
                    {SOURCE_BADGE[msg.meta.rag_source]?.label ?? msg.meta.rag_source}
                  </span>
                </div>
              )}
            </div>
            {msg.role === 'user' && (
              <div className="w-6 h-6 rounded-full bg-gnosis-muted/20 flex items-center justify-center flex-shrink-0 mt-0.5">
                <User size={12} className="text-gnosis-muted" />
              </div>
            )}
          </div>
        ))}
        <div ref={bottomRef} />
      </div>

      {/* Input */}
      <div className="flex-shrink-0 px-3 pb-3">
        <div className="flex gap-2 items-end bg-gnosis-surface border border-gnosis-border rounded-xl px-3 py-2">
          <textarea
            value={input}
            onChange={(e) => setInput(e.target.value)}
            onKeyDown={(e) => {
              if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); send(); }
            }}
            placeholder="Ask about your notes…"
            rows={1}
            className="flex-1 resize-none bg-transparent text-sm text-gnosis-fg placeholder:text-gnosis-muted outline-none min-h-[1.5rem] max-h-32"
          />
          <button
            onClick={send}
            disabled={loading || !input.trim()}
            className="p-1.5 rounded-lg bg-gnosis-accent/90 text-white hover:bg-gnosis-accent disabled:opacity-40 disabled:cursor-not-allowed transition-colors flex-shrink-0"
            aria-label="Send"
          >
            {loading ? <Loader2 size={14} className="animate-spin" /> : <Send size={14} />}
          </button>
        </div>
      </div>
    </div>
  );
}
