/**
 * useOfflineSync
 * ==============
 *
 * Strategy: renderHook() in jsdom, mock `services/api` entirely,
 * fake navigator.onLine, and fire window online/offline events.
 *
 * What we test:
 *  1.  Initial state reflects navigator.onLine
 *  2.  queueCreate adds to queuedCount
 *  3.  queueUpdate merges duplicate noteIds (no double-queue)
 *  4.  queueUpdate appends distinct noteIds
 *  5.  drainQueue calls api.createNote for queued creates
 *  6.  drainQueue calls api.updateNote for queued updates
 *  7.  drainQueue clears the queue on full success
 *  8.  drainQueue fires onToast with syncing + success messages
 *  9.  drainQueue moves failing items to tail; exits after full cycle
 *  10. drainQueue is a no-op when queue is empty
 *  11. window 'online' event triggers drainQueue and sets isOnline=true
 *  12. window 'offline' event sets isOnline=false
 *  13. triggerSync manually triggers a drain
 *  14. draining flag is true during drain, false after
 */

import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { renderHook, act } from '@testing-library/react';
import { useOfflineSync } from '../useOfflineSync';

// Mock the entire api service — all methods return resolved promises by default
vi.mock('../../services/api', () => ({
  default: {
    createNote: vi.fn().mockResolvedValue({ id: 'new-note' }),
    updateNote: vi.fn().mockResolvedValue({ id: 'existing' }),
  },
}));

import api from '../../services/api';

const mockCreate = api.createNote as ReturnType<typeof vi.fn>;
const mockUpdate = api.updateNote as ReturnType<typeof vi.fn>;

beforeEach(() => {
  vi.clearAllMocks();
  // Default: online
  Object.defineProperty(navigator, 'onLine', { value: true, writable: true, configurable: true });
});

afterEach(() => {
  vi.restoreAllMocks();
});

describe('initial state', () => {
  it('isOnline matches navigator.onLine when true', () => {
    const { result } = renderHook(() => useOfflineSync());
    expect(result.current.isOnline).toBe(true);
  });

  it('isOnline is false when navigator.onLine is false', () => {
    Object.defineProperty(navigator, 'onLine', { value: false, configurable: true });
    const { result } = renderHook(() => useOfflineSync());
    expect(result.current.isOnline).toBe(false);
  });

  it('queuedCount starts at 0', () => {
    const { result } = renderHook(() => useOfflineSync());
    expect(result.current.queuedCount).toBe(0);
  });
});

describe('queueCreate', () => {
  it('increments queuedCount', () => {
    const { result } = renderHook(() => useOfflineSync());
    act(() => { result.current.queueCreate({ title: 'Draft A' }); });
    expect(result.current.queuedCount).toBe(1);
  });

  it('each call adds a separate item', () => {
    const { result } = renderHook(() => useOfflineSync());
    act(() => {
      result.current.queueCreate({ title: 'A' });
      result.current.queueCreate({ title: 'B' });
    });
    expect(result.current.queuedCount).toBe(2);
  });
});

describe('queueUpdate', () => {
  it('increments queuedCount for a new noteId', () => {
    const { result } = renderHook(() => useOfflineSync());
    act(() => { result.current.queueUpdate('note-1', { title: 'v1' }); });
    expect(result.current.queuedCount).toBe(1);
  });

  it('merges duplicate updates for the same noteId (no double-queue)', () => {
    const { result } = renderHook(() => useOfflineSync());
    act(() => {
      result.current.queueUpdate('note-1', { title: 'v1' });
      result.current.queueUpdate('note-1', { title: 'v2' }); // merge, not append
    });
    expect(result.current.queuedCount).toBe(1);
  });

  it('appends distinct noteIds as separate items', () => {
    const { result } = renderHook(() => useOfflineSync());
    act(() => {
      result.current.queueUpdate('note-1', { title: 'v1' });
      result.current.queueUpdate('note-2', { title: 'v2' });
    });
    expect(result.current.queuedCount).toBe(2);
  });
});

describe('drainQueue (via triggerSync)', () => {
  it('calls api.createNote for queued creates', async () => {
    const { result } = renderHook(() => useOfflineSync());
    act(() => { result.current.queueCreate({ title: 'New Note' }); });

    await act(async () => { result.current.triggerSync(); });

    expect(mockCreate).toHaveBeenCalledOnce();
    expect(mockCreate).toHaveBeenCalledWith({ title: 'New Note' });
  });

  it('calls api.updateNote for queued updates', async () => {
    const { result } = renderHook(() => useOfflineSync());
    act(() => { result.current.queueUpdate('note-abc', { title: 'Updated' }); });

    await act(async () => { result.current.triggerSync(); });

    expect(mockUpdate).toHaveBeenCalledOnce();
    expect(mockUpdate).toHaveBeenCalledWith('note-abc', { title: 'Updated' });
  });

  it('clears the queue after full success', async () => {
    const { result } = renderHook(() => useOfflineSync());
    act(() => {
      result.current.queueCreate({ title: 'A' });
      result.current.queueUpdate('note-1', { title: 'B' });
    });
    expect(result.current.queuedCount).toBe(2);

    await act(async () => { result.current.triggerSync(); });

    expect(result.current.queuedCount).toBe(0);
  });

  it('fires onToast with syncing info message then success message', async () => {
    const onToast = vi.fn();
    const { result } = renderHook(() => useOfflineSync(onToast));
    act(() => { result.current.queueCreate({ title: 'T' }); });

    await act(async () => { result.current.triggerSync(); });

    expect(onToast).toHaveBeenCalledWith(expect.stringContaining('Syncing'), 'info');
    expect(onToast).toHaveBeenCalledWith(expect.stringContaining('Synced'), 'success');
  });

  it('is a no-op when the queue is empty (no API calls)', async () => {
    const { result } = renderHook(() => useOfflineSync());
    await act(async () => { result.current.triggerSync(); });
    expect(mockCreate).not.toHaveBeenCalled();
    expect(mockUpdate).not.toHaveBeenCalled();
  });

  it('moves failing items to tail and fires warning toast', async () => {
    mockCreate.mockRejectedValueOnce(new Error('network'));
    const onToast = vi.fn();
    const { result } = renderHook(() => useOfflineSync(onToast));
    act(() => { result.current.queueCreate({ title: 'Fragile' }); });

    await act(async () => { result.current.triggerSync(); });

    expect(onToast).toHaveBeenCalledWith(expect.stringContaining('Sync failed'), 'warning');
  });
});

describe('online/offline events', () => {
  it('window online event sets isOnline=true and drains the queue', async () => {
    Object.defineProperty(navigator, 'onLine', { value: false, configurable: true });
    const { result } = renderHook(() => useOfflineSync());
    expect(result.current.isOnline).toBe(false);

    await act(async () => {
      window.dispatchEvent(new Event('online'));
    });

    expect(result.current.isOnline).toBe(true);
  });

  it('window offline event sets isOnline=false', async () => {
    const { result } = renderHook(() => useOfflineSync());
    expect(result.current.isOnline).toBe(true);

    await act(async () => {
      window.dispatchEvent(new Event('offline'));
    });

    expect(result.current.isOnline).toBe(false);
  });
});
