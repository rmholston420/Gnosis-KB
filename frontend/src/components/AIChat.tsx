/**
 * AIChat: Real-time streaming chat with the Gnosis knowledge graph.
 *
 * Uses fetch() + ReadableStream for SSE so we can send the Authorization
 * header — EventSource does not support custom headers.
 * Token is read from localStorage ('gnosis_token') to mirror api.ts.
 */

import { useRef, useState, useEffect } from 'react';
import { Send, Trash2 } from 'lucide-react';
import { useAppStore } from '../store/useAppStore';
import api from '../services/api';
import type { ChatMessage } from '../types';

const RAG_MODES = ['hybrid', 'local', 'global'] as const;

function getToken(): string {
  return localStorage.getItem('gnosis_token') ?? '';
}

export default function AIChat() {
  const {
    chatMessages,
    appendChatMessage,
    updateLastAssistantMessage,
    clearChat,
    ragMode,
    setRagMode,
    sessionId,
  } = useAppStore();

  const [input, setInput] = useState('');
  const [isLoading, setIsLoading] = useState(false);
  const messagesEndRef = useRef<HTMLDivElement>(null);
  const abortRef = useRef<AbortController | null>(null);

  const scrollToBottom = () =>
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });

  useEffect(() => {
    scrollToBottom();
  }, [chatMessages]);

  const handleSend = async () => {
    if (!input.trim() || isLoading) return;

    const userMsg: ChatMessage = {
      role: 'user',
      content: input.trim(),
      timestamp: new Date().toISOString(),
    };
    appendChatMessage(userMsg);
    setInput('');
    setIsLoading(true);

    // Seed an empty assistant bubble immediately so it appears while streaming
    appendChatMessage({
      role: 'assistant',
      content: '',
      timestamp: new Date().toISOString(),
    });

    const ctrl = new AbortController();
    abortRef.current = ctrl;

    try {
      const url =
        `/api/v1/ai/stream/chat` +
        `?message=${encodeURIComponent(userMsg.content)}` +
        `&mode=${ragMode}`;

      const resp = await fetch(url, {
        signal: ctrl.signal,
        headers: {
          Authorization: `Bearer ${getToken()}`,
          Accept: 'text/event-stream',
        },
      });

      if (!resp.ok || !resp.body) {
        throw new Error(`HTTP ${resp.status}`);
      }

      const reader = resp.body.getReader();
      const decoder = new TextDecoder();
      let accumulated = '';
      let buf = '';

      while (true) {
        const { done, value } = await reader.read();
        if (done) break;

        buf += decoder.decode(value, { stream: true });
        const lines = buf.split('\n');
        buf = lines.pop() ?? '';

        for (const line of lines) {
          if (!line.startsWith('data:')) continue;
          const raw = line.slice(5).trim();
          if (raw === '[DONE]') break;
          try {
            const parsed = JSON.parse(raw);
            if (parsed.error) throw new Error(parsed.error);
            const chunk = parsed.token ?? parsed.text ?? '';
            accumulated += chunk;
            updateLastAssistantMessage(accumulated);
          } catch {
            // ignore malformed SSE lines
          }
        }
      }

      // Fallback: stream returned nothing, use POST endpoint
      if (!accumulated) {
        const resp2 = (await api.chat(
          userMsg.content,
          ragMode,
          sessionId || undefined
        )) as { answer: string };
        updateLastAssistantMessage(resp2.answer);
      }
    } catch (err) {
      if ((err as Error).name !== 'AbortError') {
        updateLastAssistantMessage(
          `Error: ${err instanceof Error ? err.message : 'Unknown error'}`
        );
      }
    } finally {
      setIsLoading(false);
      abortRef.current = null;
      scrollToBottom();
    }
  };

  const handleStop = () => {
    abortRef.current?.abort();
    setIsLoading(false);
  };

  return (
    <div className="flex flex-col h-full">
      {/* Header */}
      <div className="flex items-center justify-between px-4 py-2 border-b border-border flex-shrink-0">
        <h2 className="text-sm font-semibold text-text-primary">AI Chat</h2>
        <div className="flex items-center gap-2">
          <select
            value={ragMode}
            onChange={(e) => setRagMode(e.target.value as typeof ragMode)}
            className="text-xs bg-bg-tertiary border border-border rounded px-2 py-1 text-text-secondary"
          >
            {RAG_MODES.map((m) => (
              <option key={m} value={m}>
                {m}
              </option>
            ))}
          </select>
          <button
            onClick={clearChat}
            className="p-1.5 text-text-muted hover:text-text-primary transition-colors"
            title="Clear chat"
          >
            <Trash2 size={14} />
          </button>
        </div>
      </div>

      {/* Messages */}
      <div className="flex-1 overflow-y-auto px-4 py-3 space-y-3">
        {chatMessages.length === 0 && (
          <div className="text-center text-text-muted text-sm py-12">
            Ask anything about your knowledge base…
          </div>
        )}
        {chatMessages.map((msg, i) => (
          <div
            key={i}
            className={`flex ${
              msg.role === 'user' ? 'justify-end' : 'justify-start'
            }`}
          >
            <div
              className={`max-w-[85%] rounded-lg px-3 py-2 text-sm ${
                msg.role === 'user'
                  ? 'bg-accent-blue text-white'
                  : 'bg-bg-tertiary text-text-primary'
              }`}
            >
              <p className="whitespace-pre-wrap leading-relaxed">
                {msg.content}
                {/* blinking cursor on last assistant bubble while streaming */}
                {isLoading &&
                  i === chatMessages.length - 1 &&
                  msg.role === 'assistant' && (
                    <span className="inline-block w-0.5 h-3.5 bg-current ml-0.5 animate-pulse align-middle" />
                  )}
              </p>
            </div>
          </div>
        ))}
        <div ref={messagesEndRef} />
      </div>

      {/* Input */}
      <div className="px-4 py-3 border-t border-border flex-shrink-0">
        <div className="flex items-end gap-2">
          <textarea
            value={input}
            onChange={(e) => setInput(e.target.value)}
            onKeyDown={(e) => {
              if (e.key === 'Enter' && !e.shiftKey) {
                e.preventDefault();
                handleSend();
              }
            }}
            placeholder="Ask about your vault… (Enter to send, Shift+Enter for newline)"
            className="flex-1 bg-bg-tertiary border border-border rounded px-3 py-2 text-sm text-text-primary placeholder-text-muted outline-none resize-none focus:border-accent-blue transition-colors min-h-[38px] max-h-32"
            rows={1}
            disabled={isLoading}
          />
          {isLoading ? (
            <button
              onClick={handleStop}
              className="p-2 bg-red-500 hover:bg-red-600 text-white rounded transition-colors flex-shrink-0"
              title="Stop generation"
            >
              <span className="w-3.5 h-3.5 block bg-white rounded-sm" />
            </button>
          ) : (
            <button
              onClick={handleSend}
              disabled={!input.trim()}
              className="p-2 bg-accent-blue hover:bg-blue-600 disabled:opacity-50 text-white rounded transition-colors flex-shrink-0"
            >
              <Send size={15} />
            </button>
          )}
        </div>
      </div>
    </div>
  );
}
