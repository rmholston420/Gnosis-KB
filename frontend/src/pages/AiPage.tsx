/**
 * AiPage — AI assistant + link suggestions hub.
 *
 * AiSidebar requires noteId: string | null.
 * LinkSuggestions requires noteId, onInsert, and onDismiss.
 */
import React, { useState } from 'react';
import { AiSidebar } from '../components/ai/AiSidebar';
import { LinkSuggestions } from '../components/ai/LinkSuggestions';
import { useAppStore } from '../store/useAppStore';
import type { LinkSuggestion } from '../types';

export default function AiPage() {
  const activeNoteId = useAppStore((s) => s.activeNoteId);
  const [showLinkSuggestions, setShowLinkSuggestions] = useState(false);

  const handleInsertLink = (_suggestion: LinkSuggestion) => {
    // In the standalone AiPage there is no editor to insert into;
    // the panel is purely for review. A future version can deep-link
    // to NoteEditorPage with the suggestion pre-filled.
  };

  return (
    <div className="flex h-full overflow-hidden">
      {/* Main AI tools panel */}
      <div className="flex-1 flex flex-col overflow-hidden">
        <div className="flex items-center justify-between px-6 py-4 border-b border-gnosis-border">
          <h1 className="text-lg font-semibold text-gnosis-fg">AI Assistant</h1>
        </div>
        <div className="flex-1 overflow-hidden">
          {/* noteId={null} shows the "open a note" guard */}
          <AiSidebar
            noteId={activeNoteId ?? null}
            onInsertLink={handleInsertLink}
          />
        </div>
      </div>

      {/* Link suggestions sidebar — only shown when a note is active */}
      {activeNoteId && showLinkSuggestions && (
        <div className="w-80 border-l border-gnosis-border overflow-y-auto">
          <div className="px-4 py-3 border-b border-gnosis-border">
            <h2 className="text-sm font-medium text-gnosis-fg">Link Suggestions</h2>
          </div>
          <LinkSuggestions
            noteId={activeNoteId}
            onInsert={handleInsertLink}
            onDismiss={() => setShowLinkSuggestions(false)}
          />
        </div>
      )}

      {/* Toggle button — appears when a note is active and the panel is hidden */}
      {activeNoteId && !showLinkSuggestions && (
        <div className="absolute bottom-6 right-6">
          <button
            onClick={() => setShowLinkSuggestions(true)}
            className="px-3 py-2 rounded-lg bg-gnosis-accent text-white text-xs font-medium shadow-lg hover:opacity-90 transition-opacity"
          >
            Link Suggestions
          </button>
        </div>
      )}
    </div>
  );
}
