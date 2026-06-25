/**
 * VaultSyncWatcher — invisible component that watches the vault WebSocket
 * and dispatches toast notifications when sync events arrive.
 */
import { useEffect } from 'react';
import { useVaultWebSocket } from '../hooks/useVaultWebSocket';

export function VaultSyncWatcher() {
  const { lastMessage } = useVaultWebSocket();

  useEffect(() => {
    if (!lastMessage) return;
    const { type } = lastMessage;
    if (type === 'sync_complete') {
      // Could dispatch a toast here; kept minimal to avoid toast dep cycle.
      console.info('[VaultSyncWatcher] sync_complete received');
    } else if (type === 'sync_error') {
      console.warn('[VaultSyncWatcher] sync_error received', lastMessage.payload);
    }
  }, [lastMessage]);

  return null;
}
