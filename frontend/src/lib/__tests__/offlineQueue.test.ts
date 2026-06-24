/**
 * offlineQueue.test.ts
 * ====================
 * Unit tests for the IndexedDB-backed offline mutation queue.
 *
 * Uses fake-indexeddb (already a dev dep via idb test utils) to run
 * IndexedDB entirely in memory — no browser required.
 *
 * Cases (12):
 *  1.  count() returns 0 on a fresh DB
 *  2.  getAll() returns [] on a fresh DB
 *  3.  count() increments after SW writes a record directly
 *  4.  getAll() returns items sorted by timestamp (oldest first)
 *  5.  remove(id) deletes a single record
 *  6.  remove(unknown id) is a no-op (no error)
 *  7.  clear() removes all records
 *  8.  count() returns 0 after clear()
 *  9.  getAll() returns [] after clear()
 * 10.  multiple records survive round-trip with all fields intact
 * 11.  triggerManualSync is a no-op when serviceWorker is absent
 * 12.  triggerManualSync calls sync.register when Background Sync is present
 */

import { describe, it, expect, beforeAll, afterEach, vi } from 'vitest';
import 'fake-indexeddb/auto';
import { offlineQueue, triggerManualSync, type QueuedMutation } from '../offlineQueue';

// ── helpers ──────────────────────────────────────────────────────────────────

const DB_NAME    = 'gnosis-offline-queue';
const STORE_NAME = 'mutations';

/** Write a record directly into the IDB store (simulates the SW queuing it). */
function idbPut(item: QueuedMutation): Promise<void> {
  return new Promise((resolve, reject) => {
    const req = indexedDB.open(DB_NAME, 1);
    req.onupgradeneeded = () => {
      if (!req.result.objectStoreNames.contains(STORE_NAME)) {
        req.result.createObjectStore(STORE_NAME, { keyPath: 'id' });
      }
    };
    req.onsuccess = () => {
      const tx  = req.result.transaction(STORE_NAME, 'readwrite');
      const put = tx.objectStore(STORE_NAME).put(item);
      put.onsuccess = () => resolve();
      put.onerror   = () => reject(put.error);
    };
    req.onerror = () => reject(req.error);
  });
}

function makeMutation(overrides: Partial<QueuedMutation> = {}): QueuedMutation {
  return {
    id:        overrides.id        ?? `mut-${Math.random().toString(36).slice(2)}`,
    timestamp: overrides.timestamp ?? Date.now(),
    method:    overrides.method    ?? 'POST',
    url:       overrides.url       ?? '/api/v1/notes/',
    headers:   overrides.headers   ?? { 'Content-Type': 'application/json' },
    body:      overrides.body      ?? JSON.stringify({ title: 'test' }),
  };
}

// Wipe the fake IDB between tests so each test starts clean.
afterEach(async () => {
  await offlineQueue.clear();
});

// ── tests ─────────────────────────────────────────────────────────────────────

describe('offlineQueue', () => {
  it('count() returns 0 on a fresh store', async () => {
    expect(await offlineQueue.count()).toBe(0);
  });

  it('getAll() returns [] on a fresh store', async () => {
    expect(await offlineQueue.getAll()).toEqual([]);
  });

  it('count() increments after a record is written', async () => {
    await idbPut(makeMutation({ id: 'a' }));
    expect(await offlineQueue.count()).toBe(1);
  });

  it('getAll() returns items sorted oldest-first by timestamp', async () => {
    const newer = makeMutation({ id: 'newer', timestamp: 2000 });
    const older = makeMutation({ id: 'older', timestamp: 1000 });
    await idbPut(newer);
    await idbPut(older);
    const all = await offlineQueue.getAll();
    expect(all[0].id).toBe('older');
    expect(all[1].id).toBe('newer');
  });

  it('remove() deletes a single record by id', async () => {
    await idbPut(makeMutation({ id: 'to-delete' }));
    await idbPut(makeMutation({ id: 'keep' }));
    await offlineQueue.remove('to-delete');
    const all = await offlineQueue.getAll();
    expect(all).toHaveLength(1);
    expect(all[0].id).toBe('keep');
  });

  it('remove() with unknown id is a no-op', async () => {
    await idbPut(makeMutation({ id: 'exists' }));
    await expect(offlineQueue.remove('no-such-id')).resolves.toBeUndefined();
    expect(await offlineQueue.count()).toBe(1);
  });

  it('clear() removes all records', async () => {
    await idbPut(makeMutation({ id: 'x1' }));
    await idbPut(makeMutation({ id: 'x2' }));
    await offlineQueue.clear();
    expect(await offlineQueue.count()).toBe(0);
  });

  it('count() is 0 after clear()', async () => {
    await idbPut(makeMutation({ id: 'z' }));
    await offlineQueue.clear();
    expect(await offlineQueue.count()).toBe(0);
  });

  it('getAll() returns [] after clear()', async () => {
    await idbPut(makeMutation({ id: 'q' }));
    await offlineQueue.clear();
    expect(await offlineQueue.getAll()).toEqual([]);
  });

  it('preserves all fields on round-trip', async () => {
    const item = makeMutation({
      id:        'full-item',
      timestamp: 99999,
      method:    'PUT',
      url:       '/api/v1/notes/abc',
      headers:   { Authorization: 'Bearer tok', 'Content-Type': 'application/json' },
      body:      JSON.stringify({ title: 'Round Trip', body: 'hello' }),
    });
    await idbPut(item);
    const [result] = await offlineQueue.getAll();
    expect(result).toEqual(item);
  });

  it('triggerManualSync is a no-op when serviceWorker is absent', async () => {
    // jsdom does not define navigator.serviceWorker by default
    await expect(triggerManualSync()).resolves.toBeUndefined();
  });

  it('triggerManualSync calls sync.register when Background Sync is available', async () => {
    const register = vi.fn().mockResolvedValue(undefined);
    const mockReg  = { sync: { register } };
    // Temporarily inject a minimal serviceWorker stub
    Object.defineProperty(navigator, 'serviceWorker', {
      value:       { ready: Promise.resolve(mockReg) },
      configurable: true,
    });
    await triggerManualSync();
    expect(register).toHaveBeenCalledWith('gnosis-sync-mutations');
    // Restore
    Object.defineProperty(navigator, 'serviceWorker', {
      value:       undefined,
      configurable: true,
    });
  });
});
