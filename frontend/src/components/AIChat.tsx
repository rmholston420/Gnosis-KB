import React, { useEffect, useRef, useState } from 'react';
import type { AIChatMessage as BaseChatMessage } from '../types';

export interface MetaPayload {
  [key: string]: unknown;
  sources?: Array<{ note_id: string; title: string; score?: number }>;
  model?: string;
  error?: string;
}

export type AIChatMessage = BaseChatMessage & {
  meta?: MetaPayload;
};

interface Props {
  noteId?: string | null;
  initialMessages?: AIChatMessage[];
}

type ChatMode = 'hybrid' | 'lightrag' | 'vector' | 'naive';

const MODES: ChatMode[] = ['hybrid', 'lightrag', 'vector', 'naive'];
const INPUT_PLACEHOLDER = 'Ask your knowledge base…';
const EMPTY_TEXT = 'Ask anything about your knowledge base…';

export default function AIChat({ initialMessages = [] }: Props) {
  const [messages, setMessages] = useState<AIChatMessage[]>(initialMessages);
  const [input, setInput] = useState('');
  const [loading, setLoading] = useState(false);
  const [mode, setMode] = useState<ChatMode>('hybrid');
  const bottomRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages, loading]);

  async function handleSend() {
    const text = input.trim();
    if (!text || loading) return;

    const userMsg: AIChatMessage = { role: 'user', content: text };
    setInput('');
    setMessages((prev) => [...prev, userMsg]);
    setLoading(true);

    try {
      const res = await fetch('/api/ai/chat/stream', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          Authorization: `Bearer ${globalThis.localStorage?.getItem?.('gnosis_token') ?? ''}`,
        },
        body: JSON.stringify({ message: text, mode }),
      });

      if (!res.ok || !res.body) {
        throw new Error('Failed to get response');
      }

      const reader = res.body.getReader();
      const decoder = new TextDecoder();
      let buffer = '';
      let assistantText = '';

      setMessages((prev) => [...prev, { role: 'assistant', content: '' }]);

      while (true) {
        const { done, value } = await reader.read();
        if (done) break;

        buffer += decoder.decode(value, { stream: true });
        const parts = buffer.split('\n\n');
        buffer = parts.pop() ?? '';

        for (const part of parts) {
          const line = part
            .split('\n')
            .find((entry) => entry.trim().startsWith('data:'));
          if (!line) continue;

          const payload = line.replace(/^data:\s*/, '').trim();
          if (payload === '[DONE]') continue;

          try {
            const parsed = JSON.parse(payload) as { token?: string; reply?: string };
            const chunk = parsed.token ?? parsed.reply ?? '';
            if (!chunk) continue;
            assistantText += chunk;
            setMessages((prev) => {
              const next = [...prev];
              next[next.length - 1] = { role: 'assistant', content: assistantText };
              return next;
            });
          } catch {
            // ignore malformed SSE chunks
          }
        }
      }
    } catch (error) {
      const message = error instanceof Error ? error.message : 'Failed to get response';
      setMessages((prev) => [
        ...prev,
        { role: 'assistant', content: message, meta: { error: message } },
      ]);
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
    <div className="flex flex-col h-full" data-testid="ai-chat">
      <div className="flex-shrink-0 border-b border-border px-3 py-2 flex gap-1.5">
        {MODES.map((item) => (
          <button
            key={item}
            type="button"
            aria-label={item}
            onClick={() => setMode(item)}
            className={`px-2 py-1 rounded text-xs capitalize transition-colors ${
              mode === item
                ? 'bg-accent-teal text-white'
                : 'bg-bg-secondary text-text-primary hover:bg-bg-elevated'
            }`}
          >
            {item}
          </button>
        ))}
      </div>

      <div className="flex-1 overflow-y-auto px-3 py-2 space-y-3">
        {messages.length === 0 && (
          <p className="text-xs text-text-muted text-center mt-8">{EMPTY_TEXT}</p>
        )}
        {messages.map((msg, i) => (
          <div key={i} className={`flex ${msg.role === 'user' ? 'justify-end' : 'justify-start'}`}>
            <div
              className={`max-w-[85%] rounded px-3 py-2 text-xs leading-relaxed ${
                msg.role === 'user' ? 'bg-primary text-white' : 'bg-bg-elevated text-text-primary'
              }`}
            >
              {msg.content}
            </div>
          </div>
        ))}
        {loading && (
          <div className="flex justify-start">
            <div className="bg-bg-elevated rounded px-3 py-2 text-xs text-text-muted animate-pulse">
              Thinking…
            </div>
          </div>
        )}
        <div ref={bottomRef} />
      </div>

      <div className="flex-shrink-0 border-t border-border p-2 flex gap-1.5">
        <textarea
          className="flex-1 resize-none rounded border border-border bg-bg-secondary text-xs text-text-primary placeholder:text-text-muted px-2 py-1.5 focus:outline-none focus:border-primary"
          rows={2}
          placeholder={INPUT_PLACEHOLDER}
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
