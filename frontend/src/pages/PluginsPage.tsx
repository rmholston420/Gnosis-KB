import React, { useState } from 'react';

interface Plugin {
  id:          string;
  name:        string;
  description: string;
  version:     string;
  enabled:     boolean;
}

const BUILT_IN_PLUGINS: Plugin[] = [
  { id: 'daily-notes',    name: 'Daily Notes',      description: 'Automatically create dated daily note entries.',                     version: '1.0.0', enabled: true  },
  { id: 'graph-clusters', name: 'Graph Clusters',   description: 'Community detection and cluster colouring on the knowledge graph.', version: '1.0.0', enabled: true  },
  { id: 'spaced-rep',     name: 'Spaced Repetition', description: 'Flashcard-style review queue based on note maturity.',             version: '1.0.0', enabled: true  },
  { id: 'templates',      name: 'Templates',        description: 'Note templates with variable substitution.',                       version: '1.0.0', enabled: true  },
  { id: 'ingest',         name: 'Web Ingest',        description: 'Import web pages, PDFs, and Kindle highlights.',                   version: '0.9.0', enabled: false },
  { id: 'rag-export',     name: 'RAG Export',        description: 'Export vault as a structured dataset for external RAG pipelines.', version: '0.8.0', enabled: false },
];

export default function PluginsPage() {
  const [plugins, setPlugins] = useState<Plugin[]>(BUILT_IN_PLUGINS);

  const toggle = (id: string) =>
    setPlugins((prev) =>
      prev.map((p) => (p.id === id ? { ...p, enabled: !p.enabled } : p))
    );

  return (
    <div className="flex flex-col h-full bg-gnosis-bg text-gnosis-fg">
      <div className="px-6 pt-6 pb-4 border-b border-gnosis-border">
        <h1 className="text-xl font-semibold">Plugins</h1>
        <p className="text-sm text-gnosis-muted mt-1">
          Enable or disable built-in Gnosis-KB modules.
        </p>
      </div>

      <div className="flex-1 overflow-y-auto px-6 py-4 space-y-3">
        {plugins.map((p) => (
          <div
            key={p.id}
            className="flex items-start justify-between gap-4 p-4 rounded-lg
                       bg-gnosis-surface border border-gnosis-border"
          >
            <div className="flex-1 min-w-0">
              <div className="flex items-center gap-2">
                <span className="font-medium text-gnosis-fg">{p.name}</span>
                <span className="text-xs text-gnosis-muted">{p.version}</span>
              </div>
              <p className="text-sm text-gnosis-muted mt-0.5">{p.description}</p>
            </div>
            {/* Toggle */}
            <button
              role="switch"
              aria-checked={p.enabled}
              aria-label={`${p.enabled ? 'Disable' : 'Enable'} ${p.name}`}
              onClick={() => toggle(p.id)}
              className={[
                'relative shrink-0 w-10 h-6 rounded-full transition-colors',
                p.enabled ? 'bg-gnosis-accent' : 'bg-gnosis-border',
              ].join(' ')}
            >
              <span
                className={[
                  'absolute top-1 w-4 h-4 rounded-full bg-white shadow transition-transform',
                  p.enabled ? 'translate-x-5' : 'translate-x-1',
                ].join(' ')}
              />
            </button>
          </div>
        ))}
      </div>
    </div>
  );
}
