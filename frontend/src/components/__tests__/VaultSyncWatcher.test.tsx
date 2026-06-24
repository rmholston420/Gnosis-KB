/// <reference types="vitest/globals" />
import React from 'react';
import { render } from '@testing-library/react';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { VaultSyncWatcher } from '../VaultSyncWatcher';

vi.mock('../../hooks/useWebSocket', () => ({
  useVaultWebSocket: () => ({ lastMessage: null, send: vi.fn(), readyState: 3 }),
}));
vi.mock('../../store/aiStore', () => ({
  useAiStore: () => ({
    setVaultSyncStatus:   vi.fn(),
    setVaultSyncProgress: vi.fn(),
  }),
}));

const wrapper = ({ children }: { children: React.ReactNode }) =>
  React.createElement(QueryClientProvider, {
    client: new QueryClient(),
  }, children);

describe('VaultSyncWatcher', () => {
  it('renders null without throwing', () => {
    const { container } = render(
      React.createElement(VaultSyncWatcher),
      { wrapper },
    );
    expect(container.firstChild).toBeNull();
  });
});
