/**
 * VaultSwitcher.extended.test.tsx
 * Covers lines 163-182, 265-267, 317-319, 333-356
 * - fetchGrants triggered on mount (163-169)
 * - Outside mousedown closes dropdown (178-182)
 * - Escape key closes dropdown (265-267)
 * - ActiveVaultBanner rendered/hidden/reset (333-356)
 *
 * NOTE: the store action is `switchVault(ownerId, label)` not setActiveVault.
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
import VaultSwitcher from '../VaultSwitcher';
import { useVaultStore } from '../../store/useVaultStore';

const GRANTS = [
  { grantId: null, ownerId: 1, label: 'My Notes', permission: 'owner', pending: false },
  { grantId: 7, ownerId: 9, label: "Alice's Vault", permission: 'read', pending: false },
  { grantId: 8, ownerId: 10, label: "Bob's Pending", permission: 'read', pending: true },
];

beforeEach(() => {
  vi.mocked(fetchMyVaultGrants).mockResolvedValue(GRANTS as any);
  useVaultStore.getState().resetToOwnVault();
});
afterEach(() => { vi.clearAllMocks(); });

async function renderSwitcher() {
  let result!: ReturnType<typeof render>;
  await act(async () => {
    result = render(<MemoryRouter><VaultSwitcher /></MemoryRouter>);
  });
  return result;
}

describe('VaultSwitcher — fetchGrants on mount (lines 163-169)', () => {
  it('calls fetchMyVaultGrants on mount', async () => {
    await renderSwitcher();
    expect(fetchMyVaultGrants).toHaveBeenCalled();
  });

  it('renders vault entries after fetch', async () => {
    await renderSwitcher();
    const trigger = screen.getByRole('button');
    fireEvent.click(trigger);
    await waitFor(() => expect(screen.getByText("Alice's Vault")).toBeInTheDocument());
  });
});

describe('VaultSwitcher — outside click closes dropdown (lines 178-182)', () => {
  it('closes dropdown when clicking outside', async () => {
    await renderSwitcher();
    fireEvent.click(screen.getByRole('button'));
    await waitFor(() => expect(screen.getByText("Alice's Vault")).toBeInTheDocument());
    fireEvent.mouseDown(document.body);
    await waitFor(() => expect(screen.queryByText("Alice's Vault")).toBeNull());
  });
});

describe('VaultSwitcher — Escape key closes dropdown (lines 265-267)', () => {
  it('closes dropdown on Escape', async () => {
    await renderSwitcher();
    fireEvent.click(screen.getByRole('button'));
    await waitFor(() => expect(screen.getByText("Alice's Vault")).toBeInTheDocument());
    fireEvent.keyDown(document, { key: 'Escape' });
    await waitFor(() => expect(screen.queryByText("Alice's Vault")).toBeNull());
  });
});

describe('VaultSwitcher — ActiveVaultBanner (lines 333-356)', () => {
  it('renders banner when viewing a shared vault', async () => {
    // The store action is switchVault(ownerId, label), not setActiveVault
    await act(async () => {
      useVaultStore.getState().switchVault(9, "Alice's Vault");
    });
    await renderSwitcher();
    expect(screen.getByRole('status')).toBeInTheDocument();
    expect(screen.getByText(/alice/i)).toBeInTheDocument();
  });

  it('shows "Return to my vault" button in banner', async () => {
    await act(async () => {
      useVaultStore.getState().switchVault(9, "Alice's Vault");
    });
    await renderSwitcher();
    expect(screen.getByRole('button', { name: /return to my vault/i })).toBeInTheDocument();
  });

  it('clicking Return resets vault to own', async () => {
    await act(async () => {
      useVaultStore.getState().switchVault(9, "Alice's Vault");
    });
    await renderSwitcher();
    fireEvent.click(screen.getByRole('button', { name: /return to my vault/i }));
    await waitFor(() => expect(useVaultStore.getState().activeVaultOwnerId).toBeNull());
  });

  it('banner is absent when viewing own vault', async () => {
    await renderSwitcher();
    expect(screen.queryByRole('status')).toBeNull();
  });
});
