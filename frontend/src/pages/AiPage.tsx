/**
 * AiPage — AI assistant + link suggestions hub.
 */
import React from 'react';
import { AiSidebar } from '../components/ai/AiSidebar';
import { LinkSuggestions } from '../components/ai/LinkSuggestions';
import { useAppStore } from '../store/useAppStore';

export default function AiPage() {
  const activeNoteId = useAppStore((s) => s.activeNoteId);

  return (
    <div className="flex h-full overflow-hidden">
      {/* Main chat panel */}
      <div className="flex-1 flex flex-col overflow-hidden">
        <div className="flex items-center justify-between px-6 py-4 border-b border-gnosis-border">
          <h1 className="text-lg font-semibold text-gnosis-fg">AI Assistant</h1>
        </div>
        <div className="flex-1 overflow-hidden">
          <AiSidebar />
        </div>
      </div>

      {/* Link suggestions sidebar */}
      {activeNoteId && (
        <div className="w-72 border-l border-gnosis-border overflow-y-auto">
          <div className="px-4 py-3 border-b border-gnosis-border">
            <h2 className="text-sm font-medium text-gnosis-fg">Link Suggestions</h2>
          </div>
          <LinkSuggestions noteId={activeNoteId} />
        </div>
      )}
    </div>
  );
}
