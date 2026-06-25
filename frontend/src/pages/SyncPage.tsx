import React, { useState, useEffect } from 'react';
import { useVaultWebSocket } from '../hooks/useWebSocket';
import { useMutation } from '@tanstack/react-query';
import { triggerVaultSync } from '../services/api';
import { useAiStore } from '../store/aiStore';

type EventType = 'note_created' | 'note_updated' | 'note_deleted' | 'sync_complete' | string;

interface SyncEvent {
  timestamp: string;
  message:   string;
  type:      EventType;
}

/**
 * SyncPage — manual vault sync trigger + live WebSocket event feed.
 */
export default function SyncPage() {
  const [events, setEvents] = useState<SyncEvent[]>([]);

  const syncStatus   = useAiStore((s) => s.vaultSyncStatus);
  const syncProgress = useAiStore((s) => s.vaultSyncProgress);

  const syncMutation = useMutation({
    mutationFn: triggerVaultSync,
  });

  // useVaultWebSocket now returns { lastMessage }
  const { lastMessage } = useVaultWebSocket();

  useEffect(() => {
    if (!lastMessage) return;
    const evt = lastMessage as { type: EventType; title?: string; note_id?: string; synced?: number };
    const msg =
      evt.type === 'note_created'  ? `Created: ${evt.title ?? ''}` :
      evt.type === 'note_updated'  ? `Updated note ${evt.note_id ?? ''}` :
      evt.type === 'note_deleted'  ? `Deleted note ${evt.note_id ?? ''}` :
      evt.type === 'sync_complete' ? `Sync complete \u2014 ${evt.synced ?? 0} note(s) synced` :
      `Event: ${evt.type}`;

    setEvents((prev) => [
      { timestamp: new Date().toLocaleTimeString(), message: msg, type: evt.type },
      ...prev.slice(0, 199),
    ]);
  }, [lastMessage]);

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

          <div className="flex items-center gap-3">
            <span
              className={[
                'h-2.5 w-2.5 rounded-full',
                syncStatus === 'syncing' ? 'bg-yellow-400 animate-pulse' :
                syncStatus === 'error'   ? 'bg-red-500' :
                'bg-emerald-500',
              ].join(' ')}
            />
            {syncStatus === 'syncing' && typeof syncProgress === 'number' && (
              <span className="text-xs text-gnosis-muted tabular-nums">{syncProgress}%</span>
            )}
            <button
              onClick={() => syncMutation.mutate()}
              disabled={syncMutation.isPending || syncStatus === 'syncing'}
              className="px-4 py-2 rounded bg-gnosis-accent text-white text-sm font-medium
                         hover:opacity-90 disabled:opacity-50 transition-opacity"
            >
              {syncMutation.isPending ? 'Starting\u2026' : 'Sync Now'}
            </button>
          </div>
        </div>

        {syncStatus === 'syncing' && typeof syncProgress === 'number' && (
          <div className="mt-3 h-1 bg-gnosis-border rounded-full overflow-hidden">
            <div
              className="h-full bg-gnosis-accent transition-all duration-300"
              style={{ width: `${syncProgress}%` }}
            />
          </div>
        )}

        {syncMutation.isError && (
          <p className="mt-3 text-sm text-red-500" role="alert">
            {(syncMutation.error as Error)?.message ?? 'Sync failed'}
          </p>
        )}
      </div>

      {/* Live event feed */}
      <div className="flex-1 overflow-y-auto px-6 py-4 font-mono text-xs space-y-1">
        {events.length === 0 ? (
          <p className="text-gnosis-muted">Waiting for vault events\u2026</p>
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
