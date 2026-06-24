/**
 * AIChat.tsx — Standalone AI chat panel (used outside the editor sidebar).
 *
 * Kept intentionally minimal; the full-featured chat lives in AiSidebar.
 * We use a type alias instead of interface extension to avoid TS2430 when
 * narrowing the `meta` property against AIChatMessage from types/index.
 */
import React, { useState, useRef, useEffect } from 'react';
import type { AIChatMessage as BaseChatMessage } from '../types';
import api from '../services/api';

export interface MetaPayload {
  [key: string]: unknown;
  sources?: Array<{ note_id: string; title: string; score?: number }>;
  model?:   string;
}

// Use a type alias (not interface extension) so `meta` stays compatible
// with the base Record<string, unknown> index signature.
export type AIChatMessage = BaseChatMessage & {
  meta?: MetaPayload;
};

interface Props {
  noteId?: string | null;
  initialMessages?: AIChatMessage[];
}

export default function AIChat({ noteId, initialMessages = [] }: Props) {
  const [messages, setMessages] = useState<AIChatMessage[]>(initialMessages);
  const [input,    setInput]    = useState('');
  const [loading,  setLoading]  = useState(false);
  const bottomRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages]);

  async function handleSend() {
    const text = input.trim();
    if (!text || loading) return;
    setInput('');
    const userMsg: AIChatMessage = { role: 'user', content: text };
    setMessages((prev) => [...prev, userMsg]);
    setLoading(true);
    try {
      const history = [...messages, userMsg];
      const res = await api.chat({
        messages: history,
        note_id:  noteId ?? undefined,
      }) as { reply: string; sources?: Array<{ note_id: string; title: string; score?: number }> };
      const assistantMsg: AIChatMessage = {
        role:    'assistant',
        content: res.reply,
        meta:    res.sources ? { sources: res.sources } : undefined,
      };
      setMessages((prev) => [...prev, assistantMsg]);
    } catch (err) {
      const errMsg: AIChatMessage = {
        role:    'assistant',
        content: 'Sorry, something went wrong. Please try again.',
        meta:    { error: String(err) },
      };
      setMessages((prev) => [...prev, errMsg]);
    } finally {
      setLoading(false);
    }
  }

  function handleKeyDown(e: React.KeyboardEvent<HTMLTextAreaElement>) {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      void handleSend();
    }
  }

  return (
    <div className="flex flex-col h-full">
      <div className="flex-1 overflow-y-auto px-3 py-2 space-y-3">
        {messages.length === 0 && (
          <p className="text-xs text-text-muted text-center mt-8">
            Ask anything about your notes\u2026
          </p>
        )}
        {messages.map((msg, i) => (
          <div
            key={i}
            className={`flex ${
              msg.role === 'user' ? 'justify-end' : 'justify-start'
            }`}
          >
            <div
              className={`max-w-[85%] rounded px-3 py-2 text-xs leading-relaxed ${
                msg.role === 'user'
                  ? 'bg-primary text-white'
                  : 'bg-bg-elevated text-text-primary'
              }`}
            >
              {msg.content}
              {msg.meta?.sources && Array.isArray(msg.meta.sources) && (
                <div className="mt-1.5 pt-1.5 border-t border-white/20 space-y-0.5">
                  {(msg.meta.sources as Array<{ note_id: string; title: string }>).map((s) => (
                    <span key={s.note_id} className="block text-[10px] opacity-70">
                      \u2192 {s.title}
                    </span>
                  ))}
                </div>
              )}
            </div>
          </div>
        ))}
        {loading && (
          <div className="flex justify-start">
            <div className="bg-bg-elevated rounded px-3 py-2 text-xs text-text-muted animate-pulse">
              Thinking\u2026
            </div>
          </div>
        )}
        <div ref={bottomRef} />
      </div>

      <div className="flex-shrink-0 border-t border-border p-2 flex gap-1.5">
        <textarea
          className="flex-1 resize-none rounded border border-border bg-bg-secondary text-xs text-text-primary placeholder:text-text-muted px-2 py-1.5 focus:outline-none focus:border-primary"
          rows={2}
          placeholder="Ask about your notes\u2026"
          value={input}
          onChange={(e) => setInput(e.target.value)}
          onKeyDown={handleKeyDown}
          disabled={loading}
        />
        <button
          onClick={() => void handleSend()}
          disabled={loading || !input.trim()}
          className="px-3 py-1.5 rounded bg-primary text-white text-xs font-medium disabled:opacity-40 hover:bg-primary-hover transition-colors"
        >
          Send
        </button>
      </div>
    </div>
  );
}
