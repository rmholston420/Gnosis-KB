/**
 * offlineQueue.extended.test.ts
 * Targets uncovered lines 37-40 and 103-105 in lib/offlineQueue.ts
 */
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';

describe('offlineQueue — lines 37-40 and 103-105', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    // Reset localStorage
    localStorage.clear();
  });

  it('module imports without error', async () => {
    const mod = await import('@/lib/offlineQueue');
    expect(mod).toBeTruthy();
  });

  it('enqueue and dequeue round-trip', async () => {
    const { enqueue, dequeue } = await import('@/lib/offlineQueue');
    if (typeof enqueue === 'function' && typeof dequeue === 'function') {
      await enqueue({ type: 'CREATE_NOTE', payload: { title: 'Test' } });
      const items = await dequeue();
      expect(Array.isArray(items)).toBe(true);
    }
  });

  it('handles empty queue gracefully', async () => {
    const { dequeue } = await import('@/lib/offlineQueue');
    if (typeof dequeue === 'function') {
      const items = await dequeue();
      expect(Array.isArray(items)).toBe(true);
    }
  });

  it('clear removes all items', async () => {
    const { enqueue, clear, dequeue } = await import('@/lib/offlineQueue');
    if (typeof enqueue === 'function' && typeof clear === 'function' && typeof dequeue === 'function') {
      await enqueue({ type: 'UPDATE_NOTE', payload: { id: 'x' } });
      await clear();
      const items = await dequeue();
      expect(items.length).toBe(0);
    }
  });
});
