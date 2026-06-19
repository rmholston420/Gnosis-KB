/**
 * AiChat — Streaming RAG chat panel.
 *
 * Connects to GET /api/v1/ai/stream/chat via Server-Sent Events.
 * Each SSE chunk appends to the assistant message bubble in real time.
 * Supports three LightRAG query modes: local, global, hybrid.
 *
 * State:
 *   - messages: ChatMessage[]  — conversation history
 *   - input: string            — current user input
 *   - streaming: boolean       — SSE stream active
 *   - mode: 'local'|'global'|'hybrid'
 */
import React, {
  KeyboardEvent,
  useCallback,
  useEffect,
  useRef,
  useState,
} from "react";
import { Bot, Send, User, Zap } from "lucide-react";

/** A single message in the chat history. */
interface ChatMessage {
  id: string;
  role: "user" | "assistant";
  content: string;
  /** Partial content while streaming is in progress. */
  streaming?: boolean;
}

/** Available LightRAG query modes. */
type QueryMode = "local" | "global" | "hybrid";

/** Generate a simple unique ID for messages. */
function uid(): string {
  return Math.random().toString(36).slice(2, 10);
}

/**
 * AiChat — Full streaming chat interface for vault-aware AI conversation.
 *
 * @example
 *   // In AiChatPage.tsx:
 *   <AiChat />
 */
export function AiChat() {
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [input, setInput] = useState("");
  const [streaming, setStreaming] = useState(false);
  const [mode, setMode] = useState<QueryMode>("hybrid");
  const scrollRef = useRef<HTMLDivElement>(null);
  const eventSourceRef = useRef<EventSource | null>(null);
  const assistantIdRef = useRef<string | null>(null);

  /** Scroll to bottom whenever messages update. */
  useEffect(() => {
    scrollRef.current?.scrollTo({
      top: scrollRef.current.scrollHeight,
      behavior: "smooth",
    });
  }, [messages]);

  /** Clean up any open EventSource on unmount. */
  useEffect(() => {
    return () => {
      eventSourceRef.current?.close();
    };
  }, []);

  /** Append a chunk to the streaming assistant message. */
  const appendChunk = useCallback((msgId: string, chunk: string) => {
    setMessages((prev) =>
      prev.map((m) =>
        m.id === msgId ? { ...m, content: m.content + chunk } : m
      )
    );
  }, []);

  /** Mark the streaming message as complete. */
  const finalizeStream = useCallback((msgId: string) => {
    setMessages((prev) =>
      prev.map((m) => (m.id === msgId ? { ...m, streaming: false } : m))
    );
    setStreaming(false);
    assistantIdRef.current = null;
  }, []);

  /** Send a message and open SSE stream. */
  const sendMessage = useCallback(() => {
    const text = input.trim();
    if (!text || streaming) return;

    // Add user message
    const userMsg: ChatMessage = { id: uid(), role: "user", content: text };
    setMessages((prev) => [...prev, userMsg]);
    setInput("");

    // Add placeholder assistant message
    const assistantId = uid();
    assistantIdRef.current = assistantId;
    const assistantMsg: ChatMessage = {
      id: assistantId,
      role: "assistant",
      content: "",
      streaming: true,
    };
    setMessages((prev) => [...prev, assistantMsg]);
    setStreaming(true);

    // Open SSE connection
    const base = import.meta.env.VITE_API_BASE_URL ?? "";
    const token = localStorage.getItem("gnosis_token") ?? "";
    const url = new URL(`${base}/api/v1/ai/stream/chat`);
    url.searchParams.set("message", text);
    url.searchParams.set("mode", mode);
    // Note: EventSource doesn't support custom headers natively.
    // The SSE endpoint does not require auth (GET endpoint, localhost only).
    const es = new EventSource(url.toString());
    eventSourceRef.current = es;

    es.onmessage = (event: MessageEvent) => {
      const chunk: string = event.data;
      if (chunk === "[DONE]") {
        es.close();
        finalizeStream(assistantId);
        return;
      }
      appendChunk(assistantId, chunk + " ");
    };

    es.onerror = () => {
      es.close();
      finalizeStream(assistantId);
    };
  }, [input, streaming, mode, appendChunk, finalizeStream]);

  const handleKeyDown = useCallback(
    (e: KeyboardEvent<HTMLTextAreaElement>) => {
      if (e.key === "Enter" && !e.shiftKey) {
        e.preventDefault();
        sendMessage();
      }
    },
    [sendMessage]
  );

  const stopStream = useCallback(() => {
    eventSourceRef.current?.close();
    if (assistantIdRef.current) {
      finalizeStream(assistantIdRef.current);
    }
  }, [finalizeStream]);

  return (
    <div className="ai-chat">
      {/* Header */}
      <div className="ai-chat__header">
        <Zap size={18} />
        <span>Gnosis AI Chat</span>
        <div className="ai-chat__mode-selector">
          {(["local", "global", "hybrid"] as QueryMode[]).map((m) => (
            <button
              key={m}
              className={`ai-chat__mode-btn ${mode === m ? "active" : ""}`}
              onClick={() => setMode(m)}
              title={{
                local: "Entity-specific lookups",
                global: "Thematic synthesis across vault",
                hybrid: "Combined local + global (default)",
              }[m]}
            >
              {m}
            </button>
          ))}
        </div>
      </div>

      {/* Message list */}
      <div className="ai-chat__messages" ref={scrollRef}>
        {messages.length === 0 && (
          <div className="ai-chat__empty">
            <Bot size={40} />
            <p>Ask anything about your vault.</p>
            <p className="ai-chat__hint">
              Use <strong>hybrid</strong> mode for most questions,{" "}
              <strong>local</strong> for specific notes, <strong>global</strong>{" "}
              for themes.
            </p>
          </div>
        )}

        {messages.map((msg) => (
          <div
            key={msg.id}
            className={`ai-chat__message ai-chat__message--${msg.role}`}
          >
            <div className="ai-chat__message-icon">
              {msg.role === "user" ? <User size={16} /> : <Bot size={16} />}
            </div>
            <div className="ai-chat__message-content">
              {msg.content || (msg.streaming ? (
                <span className="ai-chat__cursor" aria-label="Thinking">&#9646;</span>
              ) : null)}
              {msg.streaming && msg.content && (
                <span className="ai-chat__cursor" aria-hidden="true">&#9646;</span>
              )}
            </div>
          </div>
        ))}
      </div>

      {/* Input area */}
      <div className="ai-chat__input-area">
        <textarea
          className="ai-chat__textarea"
          value={input}
          onChange={(e) => setInput(e.target.value)}
          onKeyDown={handleKeyDown}
          placeholder="Ask about your vault… (Enter to send, Shift+Enter for newline)"
          rows={3}
          disabled={streaming}
          aria-label="Chat message input"
        />
        <div className="ai-chat__actions">
          {streaming ? (
            <button
              className="ai-chat__stop-btn"
              onClick={stopStream}
              aria-label="Stop generating"
            >
              Stop
            </button>
          ) : (
            <button
              className="ai-chat__send-btn"
              onClick={sendMessage}
              disabled={!input.trim()}
              aria-label="Send message"
            >
              <Send size={18} />
            </button>
          )}
        </div>
      </div>
    </div>
  );
}
