import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render } from '@testing-library/react';
import { createElement } from 'react';

// Mock the WebSocket hook so it doesn’t actually connect
vi.mock('../../hooks/useWebSocket', () => ({
  useVaultWebSocket: vi.fn(),
}));

import VaultSyncWatcher from '../VaultSyncWatcher';
import { useVaultWebSocket } from '../../hooks/useWebSocket';

beforeEach(() => vi.clearAllMocks());

describe('VaultSyncWatcher', () => {
  it('mounts without error and calls useVaultWebSocket', () => {
    render(createElement(VaultSyncWatcher));
    expect(useVaultWebSocket).toHaveBeenCalledTimes(1);
  });

  it('renders nothing visible (null render)', () => {
    const { container } = render(createElement(VaultSyncWatcher));
    expect(container.firstChild).toBeNull();
  });
});
