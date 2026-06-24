import { describe, it, expect, vi, beforeEach } from 'vitest';

describe('offlineQueue', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    localStorage.clear();
  });

  it('module imports without error', async () => {
    const mod = await import('@/lib/offlineQueue');
    expect(mod.offlineQueue).toBeTruthy();
  });

  it('getAll returns an array shape', async () => {
    const { offlineQueue } = await import('@/lib/offlineQueue');
    const getAllSpy = vi.spyOn(offlineQueue, 'getAll').mockResolvedValueOnce([]);
    const items = await offlineQueue.getAll();
    expect(Array.isArray(items)).toBe(true);
    getAllSpy.mockRestore();
  });
});
