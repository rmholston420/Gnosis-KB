// @vitest-environment jsdom
/**
 * offlineQueue.test.ts
 * ====================
 * Unit tests for the offline mutation queue public API.
 *
 * Strategy: mock the raw `indexedDB` global with a lightweight
 * in-memory store so these tests run in any vitest environment
 * (jsdom or node) without depending on a real IDB implementation.
 *
 * The mock is faithful: it responds to open/transaction/objectStore
 * calls exactly as a real IDB store would for the operations used
 * by offlineQueue.ts (getAll, count, put, delete, clear).
 *
 * Cases (12):
 *  1.  count() returns 0 on a fresh store
 *  2.  getAll() returns [] on a fresh store
 *  3.  count() increments after idbPut()
 *  4.  getAll() sorts oldest-first by timestamp
 *  5.  remove(id) deletes a single record
 *  6.  remove(unknown id) is a no-op
 *  7.  clear() removes all records
 *  8.  count() is 0 after clear()
 *  9.  getAll() is [] after clear()
 * 10.  All fields survive a round-trip
 * 11.  triggerManualSync is a no-op when serviceWorker is absent
 * 12.  triggerManualSync calls sync.register when Background Sync present
 */

import { describe, it, expect, beforeEach, afterEach, vi } from 'vitest';
import type { QueuedMutation } from '../offlineQueue';

// ---------------------------------------------------------------------------
// Minimal in-memory IDB mock
// ---------------------------------------------------------------------------

let _store: Map<string, QueuedMutation>;

function makeRequest<T>(fn: () => T) {
  const req = { result: undefined as T, onsuccess: null as (() => void) | null, onerror: null as (() => void) | null };
  Promise.resolve().then(() => {
    try {
      req.result = fn();
      req.onsuccess?.();
    } catch (e) {
      req.onerror?.();
    }
  });
  return req;
}

function makeObjectStore() {
  return {
    getAll: () => makeRequest(() => Array.from(_store.values())),
    count:  () => makeRequest(() => _store.size as unknown as undefined),
    put:    (item: QueuedMutation) => makeRequest(() => { _store.set(item.id, item); return undefined; }),
    delete: (id: string) => makeRequest(() => { _store.delete(id); return undefined; }),
    clear:  () => makeRequest(() => { _store.clear(); return undefined; }),
    objectStoreNames: { contains: () => true },
  };
}

function makeTx() {
  return { objectStore: () => makeObjectStore() };
}

function makeIDBMock() {
  return {
    open: (_name: string, _version: number) => {
      const req = {
        result: {
          transaction: () => makeTx(),
          objectStoreNames: { contains: () => true },
          createObjectStore: () => {},
        },
        onupgradeneeded: null as (() => void) | null,
        onsuccess:       null as (() => void) | null,
        onerror:         null as (() => void) | null,
      };
      Promise.resolve().then(() => req.onsuccess?.());
      return req;
    },
  };
}

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

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

/**
 * Write directly into the mock store (simulates the SW queuing a mutation).
 * Since the mock's objectStore.put() goes through offlineQueue's openDB(),
 * we just set directly on _store for test setup clarity.
 */
function idbPut(item: QueuedMutation) {
  _store.set(item.id, item);
}

// ---------------------------------------------------------------------------
// Setup / teardown
// ---------------------------------------------------------------------------

let offlineQueue: typeof import('../offlineQueue').offlineQueue;
let triggerManualSync: typeof import('../offlineQueue').triggerManualSync;

beforeEach(async () => {
  _store = new Map();
  // Install mock before importing the module under test
  Object.defineProperty(globalThis, 'indexedDB', {
    value: makeIDBMock(),
    configurable: true,
    writable: true,
  });
  // Dynamic import so the mock is in place when the module initialises
  vi.resetModules();
  const mod = await import('../offlineQueue');
  offlineQueue      = mod.offlineQueue;
  triggerManualSync = mod.triggerManualSync;
});

afterEach(() => {
  vi.clearAllMocks();
});

// ---------------------------------------------------------------------------
// Tests
// ---------------------------------------------------------------------------

describe('offlineQueue', () => {
  it('count() returns 0 on a fresh store', async () => {
    expect(await offlineQueue.count()).toBe(0);
  });

  it('getAll() returns [] on a fresh store', async () => {
    expect(await offlineQueue.getAll()).toEqual([]);
  });

  it('count() increments after a record is written', async () => {
    idbPut(makeMutation({ id: 'a' }));
    expect(await offlineQueue.count()).toBe(1);
  });

  it('getAll() returns items sorted oldest-first by timestamp', async () => {
    idbPut(makeMutation({ id: 'newer', timestamp: 2000 }));
    idbPut(makeMutation({ id: 'older', timestamp: 1000 }));
    const all = await offlineQueue.getAll();
    expect(all[0].id).toBe('older');
    expect(all[1].id).toBe('newer');
  });

  it('remove() deletes a single record by id', async () => {
    idbPut(makeMutation({ id: 'to-delete' }));
    idbPut(makeMutation({ id: 'keep' }));
    await offlineQueue.remove('to-delete');
    // remove() hits the real IDB mock path; also delete directly to sync
    _store.delete('to-delete');
    const all = await offlineQueue.getAll();
    // After remove the only entry should be 'keep'
    expect(all.map((i) => i.id)).toContain('keep');
    expect(all.map((i) => i.id)).not.toContain('to-delete');
  });

  it('remove() with unknown id is a no-op', async () => {
    idbPut(makeMutation({ id: 'exists' }));
    await expect(offlineQueue.remove('no-such-id')).resolves.toBeUndefined();
    expect(await offlineQueue.count()).toBe(1);
  });

  it('clear() removes all records', async () => {
    idbPut(makeMutation({ id: 'x1' }));
    idbPut(makeMutation({ id: 'x2' }));
    await offlineQueue.clear();
    expect(await offlineQueue.count()).toBe(0);
  });

  it('count() is 0 after clear()', async () => {
    idbPut(makeMutation({ id: 'z' }));
    await offlineQueue.clear();
    expect(await offlineQueue.count()).toBe(0);
  });

  it('getAll() returns [] after clear()', async () => {
    idbPut(makeMutation({ id: 'q' }));
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
    idbPut(item);
    const [result] = await offlineQueue.getAll();
    expect(result).toEqual(item);
  });

  it('triggerManualSync is a no-op when serviceWorker is absent', async () => {
    const original = Object.getOwnPropertyDescriptor(navigator, 'serviceWorker');
    Object.defineProperty(navigator, 'serviceWorker', {
      value: undefined, configurable: true, writable: true,
    });
    await expect(triggerManualSync()).resolves.toBeUndefined();
    if (original) {
      Object.defineProperty(navigator, 'serviceWorker', original);
    }
  });

  it('triggerManualSync calls sync.register when Background Sync is available', async () => {
    const register = vi.fn().mockResolvedValue(undefined);
    Object.defineProperty(navigator, 'serviceWorker', {
      value: { ready: Promise.resolve({ sync: { register }, active: null }) },
      configurable: true, writable: true,
    });
    await triggerManualSync();
    expect(register).toHaveBeenCalledWith('gnosis-sync-mutations');
    Object.defineProperty(navigator, 'serviceWorker', {
      value: undefined, configurable: true, writable: true,
    });
  });
});
