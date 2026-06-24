/// <reference types="vitest/globals" />
import { useAppStore } from '../useAppStore';

const reset = () => useAppStore.setState({
  isAuthenticated: false,
  user: null,
  sidebarOpen: true,
  sidebarCollapsed: false,
  chatMessages: [],
  sessionId: null,
});

describe('useAppStore', () => {
  beforeEach(() => { reset(); });

  it('starts unauthenticated', () => {
    expect(useAppStore.getState().isAuthenticated).toBe(false);
    expect(useAppStore.getState().user).toBeNull();
  });

  it('setUser authenticates the session', () => {
    useAppStore.getState().setUser({ username: 'rinpoche', email: 'r@gnosis.local' });
    expect(useAppStore.getState().isAuthenticated).toBe(true);
    expect(useAppStore.getState().user?.username).toBe('rinpoche');
  });

  it('logout clears auth state', () => {
    useAppStore.getState().setUser({ username: 'rinpoche', email: 'r@gnosis.local' });
    useAppStore.getState().logout();
    expect(useAppStore.getState().isAuthenticated).toBe(false);
    expect(useAppStore.getState().user).toBeNull();
  });

  it('toggleSidebar flips sidebarOpen', () => {
    const before = useAppStore.getState().sidebarOpen;
    useAppStore.getState().toggleSidebar();
    expect(useAppStore.getState().sidebarOpen).toBe(!before);
  });

  it('appendChatMessage adds to chatMessages', () => {
    useAppStore.getState().appendChatMessage({ role: 'user', content: 'hello' });
    expect(useAppStore.getState().chatMessages).toHaveLength(1);
  });

  it('clearChat empties chatMessages', () => {
    useAppStore.getState().appendChatMessage({ role: 'user', content: 'hello' });
    useAppStore.getState().clearChat();
    expect(useAppStore.getState().chatMessages).toHaveLength(0);
  });
});
