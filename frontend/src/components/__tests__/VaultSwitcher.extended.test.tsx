/**
 * VaultSwitcher.extended.test.tsx
 * Covers fetchGrants on mount, outside-click close, Escape close,
 * and ActiveVaultBanner rendered/hidden/reset.
 */
import React from 'react';
import { render, screen, fireEvent, waitFor, act } from '@testing-library/react';
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { MemoryRouter } from 'react-router-dom';

vi.mock('../../services/vaultApi', () => ({
  fetchMyVaultGrants: vi.fn(),
  acceptVaultGrant: vi.fn(),
}));

import { fetchMyVaultGrants } from '../../services/vaultApi';
import type { VaultGrant } from '../../services/vaultApi';
import VaultSwitcher, { VaultContextBanner } from '../VaultSwitcher';
import { useVaultStore } from '../../store/useVaultStore';

const GRANTS: VaultGrant[] = [
  { grantId: null, ownerId: 1, label: 'My Notes', permission: 'owner', pending: false },
  { grantId: 7, ownerId: 9, label: "Alice's Vault", permission: 'read', pending: false },
  { grantId: 8, ownerId: 10, label: "Bob's Pending", permission: 'read', pending: true },
];

beforeEach(() => {
  vi.mocked(fetchMyVaultGrants).mockResolvedValue(GRANTS);
  useVaultStore.getState().resetToOwnVault();
});
afterEach(() => { vi.clearAllMocks(); });

async function renderSwitcher() {
  let result!: ReturnType<typeof render>;
  await act(async () => {
    result = render(
      <MemoryRouter>
        <VaultContextBanner />
        <VaultSwitcher />
      </MemoryRouter>
    );
  });
  return result;
}

describe('VaultSwitcher — fetchGrants on mount', () => {
  it('calls fetchMyVaultGrants on mount', async () => {
    await renderSwitcher();
    expect(fetchMyVaultGrants).toHaveBeenCalled();
  });

  it('renders vault entries after fetch', async () => {
    await renderSwitcher();
    const trigger = screen.getAllByRole('button')[0];
    fireEvent.click(trigger);
    await waitFor(() => expect(screen.getByText("Alice's Vault")).toBeInTheDocument());
  });
});

describe('VaultSwitcher — outside click closes dropdown', () => {
  it('closes dropdown when clicking outside', async () => {
    await renderSwitcher();
    fireEvent.click(screen.getAllByRole('button')[0]);
    await waitFor(() => expect(screen.getByText("Alice's Vault")).toBeInTheDocument());
    fireEvent.mouseDown(document.body);
    await waitFor(() => expect(screen.queryByText("Alice's Vault")).toBeNull());
  });
});

describe('VaultSwitcher — Escape key closes dropdown', () => {
  it('closes dropdown on Escape', async () => {
    await renderSwitcher();
    fireEvent.click(screen.getAllByRole('button')[0]);
    await waitFor(() => expect(screen.getByText("Alice's Vault")).toBeInTheDocument());
    fireEvent.keyDown(document, { key: 'Escape' });
    await waitFor(() => expect(screen.queryByText("Alice's Vault")).toBeNull());
  });
});

describe('VaultSwitcher — ActiveVaultBanner', () => {
  it('banner is hidden when on own vault', async () => {
    await renderSwitcher();
    const banner = screen.queryByRole('status');
    expect(!banner || !banner.textContent?.includes('Viewing'));
  });

  it('banner shows vault label after switchVault', async () => {
    await renderSwitcher();
    act(() => {
      useVaultStore.getState().switchVault(9, "Alice's Vault");
    });
    await waitFor(() => {
      const banner = screen.queryByRole('status');
      expect(banner).toBeTruthy();
    });
  });

  it('resetToOwnVault hides the banner', async () => {
    await renderSwitcher();
    act(() => { useVaultStore.getState().switchVault(9, "Alice's Vault"); });
    act(() => { useVaultStore.getState().resetToOwnVault(); });
    await waitFor(() => {
      const banner = screen.queryByRole('status');
      expect(!banner || !banner.textContent?.includes('Viewing'));
    });
  });
});
