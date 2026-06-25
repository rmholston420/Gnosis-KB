import React from 'react';
import AIChat from '../components/AIChat';

export default function AIChatPage() {
  return (
    <div data-testid="ai-chat" className="flex flex-col h-full bg-gnosis-bg">
      <div className="px-6 pt-6 pb-2 border-b border-gnosis-border">
        <h1 className="text-xl font-semibold text-gnosis-fg">AI Chat</h1>
        <p className="text-sm text-gnosis-muted mt-1">
          Ask questions about your vault using hybrid RAG retrieval.
        </p>
      </div>
      <div className="flex-1 overflow-hidden">
        <AIChat />
      </div>
    </div>
  );
}
