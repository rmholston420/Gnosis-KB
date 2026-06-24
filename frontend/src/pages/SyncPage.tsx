import React, { useState, useCallback } from 'react';
import { useVaultWebSocket, type VaultEvent } from '../hooks/useWebSocket';
import { triggerVaultSync } from '../api/notes';

interface SyncEvent {
  timestamp: string;
  message: string;
  type: VaultEvent['type'];
}

/**
 * SyncPage — manual vault sync trigger + live event feed.
 * Connects to the vault watcher WebSocket and shows a real-time log.
 */
export default function SyncPage() {
  const [events,  setEvents]  = useState<SyncEvent[]>([]);
  const [syncing, setSyncing] = useState(false);
  const [error,   setError]   = useState<string | null>(null);

  const onEvent = useCallback((evt: VaultEvent) => {
    const msg =
      evt.type === 'note_created'  ? `Created: ${evt.title}` :
      evt.type === 'note_updated'  ? `Updated note ${evt.note_id}` :
      evt.type === 'note_deleted'  ? `Deleted note ${evt.note_id}` :
      evt.type === 'sync_complete' ? `Sync complete — ${evt.synced} note(s) synced` :
      'Unknown event';

    setEvents((prev) => [
      { timestamp: new Date().toLocaleTimeString(), message: msg, type: evt.type },
      ...prev.slice(0, 199),
    ]);
  }, []);

  useVaultWebSocket(onEvent);

  const handleSync = useCallback(async () => {
    setSyncing(true);
    setError(null);
    try {
      await triggerVaultSync();
    } catch (e) {
      setError((e as Error).message ?? 'Sync failed');
    } finally {
      setSyncing(false);
    }
  }, []);

  return (
    <div className="flex flex-col h-full bg-gnosis-bg text-gnosis-fg">
      {/* Header */}
      <div className="px-6 pt-6 pb-4 border-b border-gnosis-border">
        <div className="flex items-center justify-between">
          <div>
            <h1 className="text-xl font-semibold">Vault Sync</h1>
            <p className="text-sm text-gnosis-muted mt-1">
              Trigger a manual sync or watch live vault events.
            </p>
          </div>
          <button
            onClick={handleSync}
            disabled={syncing}
            className="px-4 py-2 rounded bg-gnosis-accent text-white text-sm font-medium
                       hover:opacity-90 disabled:opacity-50 transition-opacity"
          >
            {syncing ? 'Syncing…' : 'Sync Now'}
          </button>
        </div>
        {error && (
          <p className="mt-3 text-sm text-red-500" role="alert">{error}</p>
        )}
      </div>

      {/* Event feed */}
      <div className="flex-1 overflow-y-auto px-6 py-4 font-mono text-xs space-y-1">
        {events.length === 0 ? (
          <p className="text-gnosis-muted">Waiting for vault events…</p>
        ) : (
          events.map((e, i) => (
            <div key={i} className="flex gap-3">
              <span className="text-gnosis-muted shrink-0">{e.timestamp}</span>
              <span className={[
                e.type === 'sync_complete' ? 'text-green-500' :
                e.type === 'note_deleted'  ? 'text-red-400'   :
                'text-gnosis-fg',
              ].join('')}>
                {e.message}
              </span>
            </div>
          ))
        )}
      </div>
    </div>
  );
}
