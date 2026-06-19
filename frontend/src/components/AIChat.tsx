/**
 * AIChat: Real-time streaming chat with the Gnosis knowledge graph.
 *
 * Uses Server-Sent Events (SSE) via EventSource for streaming.
 * Falls back to POST /ai/chat for non-streaming response.
 */

import { useRef, useState } from 'react';
import { Send, Trash2 } from 'lucide-react';
import { useAppStore } from '../store/useAppStore';
import api from '../services/api';
import type { ChatMessage } from '../types';

const RAG_MODES = ['hybrid', 'local', 'global'] as const;

export default function AIChat() {
  const { chatMessages, appendChatMessage, clearChat, ragMode, setRagMode, sessionId } = useAppStore();
  const [input, setInput] = useState('');
  const [isLoading, setIsLoading] = useState(false);
  const messagesEndRef = useRef<HTMLDivElement>(null);

  const scrollToBottom = () =>
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });

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
    scrollToBottom();

    try {
      // Use SSE streaming
      let accumulated = '';
      const assistantMsg: ChatMessage = {
        role: 'assistant',
        content: '',
        timestamp: new Date().toISOString(),
      };

      // Try streaming via EventSource
      const streamUrl = `/api/v1/ai/stream/chat?message=${encodeURIComponent(userMsg.content)}&mode=${ragMode}`;
      const eventSource = new EventSource(streamUrl);

      await new Promise<void>((resolve, reject) => {
        eventSource.onmessage = (event) => {
          if (event.data === '[DONE]') {
            eventSource.close();
            resolve();
            return;
          }
          try {
            const parsed = JSON.parse(event.data);
            if (parsed.error) {
              eventSource.close();
              reject(new Error(parsed.error));
              return;
            }
            accumulated += parsed.text || '';
            assistantMsg.content = accumulated;
          } catch {
            // ignore parse errors
          }
        };
        eventSource.onerror = () => {
          eventSource.close();
          resolve(); // fallback
        };
      });

      if (!accumulated) {
        // Fallback to non-streaming
        const resp = await api.chat(userMsg.content, ragMode, sessionId || undefined) as { answer: string };
        assistantMsg.content = resp.answer;
      }

      appendChatMessage(assistantMsg);
    } catch (err) {
      appendChatMessage({
        role: 'assistant',
        content: `Error: ${err instanceof Error ? err.message : 'Unknown error'}`,
      });
    } finally {
      setIsLoading(false);
      scrollToBottom();
    }
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
              <option key={m} value={m}>{m}</option>
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
            Ask anything about your knowledge base...
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
              <p className="whitespace-pre-wrap leading-relaxed">{msg.content}</p>
            </div>
          </div>
        ))}
        {isLoading && (
          <div className="flex justify-start">
            <div className="bg-bg-tertiary rounded-lg px-3 py-2">
              <div className="flex gap-1">
                {[0, 1, 2].map((i) => (
                  <div
                    key={i}
                    className="w-1.5 h-1.5 rounded-full bg-text-muted animate-bounce"
                    style={{ animationDelay: `${i * 150}ms` }}
                  />
                ))}
              </div>
            </div>
          </div>
        )}
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
            placeholder="Ask about your vault... (Enter to send, Shift+Enter for newline)"
            className="flex-1 bg-bg-tertiary border border-border rounded px-3 py-2 text-sm text-text-primary placeholder-text-muted outline-none resize-none focus:border-accent-blue transition-colors min-h-[38px] max-h-32"
            rows={1}
            disabled={isLoading}
          />
          <button
            onClick={handleSend}
            disabled={isLoading || !input.trim()}
            className="p-2 bg-accent-blue hover:bg-blue-600 disabled:opacity-50 text-white rounded transition-colors flex-shrink-0"
          >
            <Send size={15} />
          </button>
        </div>
      </div>
    </div>
  );
}
