import React, { useState } from 'react';
import AiSidebar from '../components/ai/AiSidebar';
import LinkSuggestions from '../components/ai/LinkSuggestions';

type AiTab = 'assistant' | 'links';

/**
 * AiPage — AI tools hub.
 * Tab 1: AiSidebar (critique, summarise, tag suggestions).
 * Tab 2: LinkSuggestions (wikilink recommendations across vault).
 */
export default function AiPage() {
  const [tab, setTab] = useState<AiTab>('assistant');

  return (
    <div className="flex flex-col h-full bg-gnosis-bg">
      {/* Header */}
      <div className="px-6 pt-6 pb-0 border-b border-gnosis-border">
        <h1 className="text-xl font-semibold text-gnosis-fg mb-4">AI Tools</h1>
        <div className="flex gap-1" role="tablist">
          {(['assistant', 'links'] as AiTab[]).map((t) => (
            <button
              key={t}
              role="tab"
              aria-selected={tab === t}
              onClick={() => setTab(t)}
              className={[
                'px-4 py-2 text-sm rounded-t transition-colors capitalize',
                tab === t
                  ? 'bg-gnosis-surface text-gnosis-fg font-medium border border-b-0 border-gnosis-border'
                  : 'text-gnosis-muted hover:text-gnosis-fg',
              ].join(' ')}
            >
              {t === 'assistant' ? 'Assistant' : 'Link Suggestions'}
            </button>
          ))}
        </div>
      </div>

      {/* Body */}
      <div className="flex-1 overflow-y-auto">
        {tab === 'assistant' ? (
          <AiSidebar />
        ) : (
          <div className="p-6">
            <p className="text-sm text-gnosis-muted mb-4">
              Select a note to see AI-powered link suggestions.
            </p>
            <LinkSuggestions noteId={null} />
          </div>
        )}
      </div>
    </div>
  );
}
