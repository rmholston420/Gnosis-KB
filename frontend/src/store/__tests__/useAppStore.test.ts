import { describe, it, expect, beforeEach } from 'vitest';
import { act, renderHook } from '@testing-library/react';
import { useAppStore } from '../useAppStore';

beforeEach(() => {
  // Reset store to initial state between tests
  useAppStore.setState({ isAuthenticated: false, user: null });
});

describe('useAppStore — auth slice', () => {
  it('starts unauthenticated', () => {
    const { result } = renderHook(() => useAppStore());
    expect(result.current.isAuthenticated).toBe(false);
    expect(result.current.user).toBeNull();
  });

  it('setUser marks authenticated', () => {
    const { result } = renderHook(() => useAppStore());
    act(() => result.current.setUser({ username: 'rinpoche', email: 'r@gnosis.kb' }));
    expect(result.current.isAuthenticated).toBe(true);
    expect(result.current.user?.username).toBe('rinpoche');
  });

  it('logout clears user', () => {
    const { result } = renderHook(() => useAppStore());
    act(() => result.current.setUser({ username: 'rinpoche', email: 'r@gnosis.kb' }));
    act(() => result.current.logout());
    expect(result.current.isAuthenticated).toBe(false);
    expect(result.current.user).toBeNull();
  });
});

describe('useAppStore — sidebar slice', () => {
  it('toggles sidebar', () => {
    const { result } = renderHook(() => useAppStore());
    const initial = result.current.sidebarOpen;
    act(() => result.current.toggleSidebar());
    expect(result.current.sidebarOpen).toBe(!initial);
  });
});
