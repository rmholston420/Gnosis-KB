/**
 * AiChat — Streaming RAG chat panel.
 *
 * Connects to the backend SSE endpoint via EventSource.
 * Token is appended as a query param because EventSource
 * does not support custom request headers.
 */

import React, { useState, useRef, useEffect } from 'react';
import { Send, Loader2, Bot, User, Cpu } from 'lucide-react';
import type { ChatMessage } from '../../types';

type ChatMode = 'hybrid' | 'lightrag' | 'vector' | 'naive';

interface AIChatMessage extends ChatMessage {
  isStreaming?: boolean;
}

export default function AiChat() {
  const [messages,  setMessages]  = useState<AIChatMessage[]>([]);
  const [input,     setInput]     = useState('');
  const [loading,   setLoading]   = useState(false);
  const [mode,      setMode]      = useState<ChatMode>('hybrid');
  const bottomRef  = useRef<HTMLDivElement>(null);
  const esRef      = useRef<EventSource | null>(null);
  const sessionRef = useRef<string>(crypto.randomUUID());

  // Cleanup EventSource on unmount
  useEffect(() => () => { esRef.current?.close(); }, []);

  async function send() {
    const text = input.trim();
    if (!text || loading) return;

    setMessages((prev) => [...prev, { role: 'user', content: text }]);
    setInput('');
    setLoading(true);

    // Placeholder for assistant message
    const assistantIdx = messages.length + 1;
    setMessages((prev) => [...prev, { role: 'assistant', content: '', isStreaming: true }]);

    // Close any existing connection
    esRef.current?.close();

    // Open SSE connection
    const base = import.meta.env.VITE_API_BASE_URL ?? "";
    const url = new URL(`${base}/api/v1/ai/stream/chat`);
    url.searchParams.set("message", text);
    url.searchParams.set("mode", mode);
    url.searchParams.set("session_id", sessionRef.current);
    // Note: EventSource doesn't support custom headers natively.
    // The backend must accept the token via query param or cookie.

    const es = new EventSource(url.toString());
    esRef.current = es;
    let accumulated = '';

    es.onmessage = (event: MessageEvent) => {
      const data = event.data as string;
      if (data === '[DONE]') {
        es.close();
        setLoading(false);
        setMessages((prev) =>
          prev.map((m, i) => i === assistantIdx ? { ...m, isStreaming: false } : m)
        );
        bottomRef.current?.scrollIntoView({ behavior: 'smooth' });
        return;
      }
      try {
        const parsed = JSON.parse(data) as { token?: string; error?: string };
        if (parsed.error) {
          accumulated += `\n\n*Error: ${parsed.error}*`;
        } else if (parsed.token) {
          accumulated += parsed.token;
        }
        setMessages((prev) =>
          prev.map((m, i) => i === assistantIdx ? { ...m, content: accumulated } : m)
        );
        bottomRef.current?.scrollIntoView({ behavior: 'smooth' });
      } catch {
        // ignore non-JSON lines
      }
    };

    es.onerror = () => {
      es.close();
      setLoading(false);
      setMessages((prev) =>
        prev.map((m, i) =>
          i === assistantIdx
            ? { ...m, content: accumulated || '*Connection error — please try again.*', isStreaming: false }
            : m
        )
      );
    };
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
            <div
              className={`max-w-[75%] rounded-lg px-3 py-2 text-sm leading-relaxed ${
                msg.role === 'user'
                  ? 'bg-accent-teal text-white ml-auto'
                  : 'bg-bg-secondary text-text-primary'
              }`}
            >
              {msg.content || (
                <span className="inline-flex gap-1">
                  <span className="animate-bounce" style={{ animationDelay: '0ms'   }}>·</span>
                  <span className="animate-bounce" style={{ animationDelay: '150ms' }}>·</span>
                  <span className="animate-bounce" style={{ animationDelay: '300ms' }}>·</span>
                </span>
              )}
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
            placeholder="Ask your knowledge base…"
            rows={1}
            className="flex-1 resize-none rounded-lg bg-bg-secondary px-3 py-2 text-sm focus:outline-none border border-border-default min-h-[36px] max-h-[120px]"
          />
          <button
            onClick={() => void send()}
            disabled={loading || !input.trim()}
            className="flex-shrink-0 rounded-lg bg-accent-teal p-2 text-white hover:bg-accent-teal/80 disabled:opacity-50 transition-colors"
          >
            {loading ? <Loader2 size={16} className="animate-spin" /> : <Send size={16} />}
          </button>
        </div>
      </div>
    </div>
  );
}
