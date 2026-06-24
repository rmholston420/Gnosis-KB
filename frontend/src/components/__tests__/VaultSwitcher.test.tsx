/**
 * VaultSwitcher
 * =============
 * Tests the vault-switcher dropdown that lets users switch between their own
 * vault and vaults they have been granted access to.
 *
 * Strategy:
 *  - Mock vaultApi (fetchMyVaultGrants, acceptVaultGrant)
 *  - Render with MemoryRouter
 *  - Interact via fireEvent / userEvent
 *
 * What we test (10 cases):
 *  1.  Renders the switcher trigger button
 *  2.  Dropdown is closed by default
 *  3.  Clicking trigger opens the dropdown
 *  4.  Own-vault entry is shown with 'You' badge
 *  5.  Shared vault entries are listed
 *  6.  Pending grant shows an 'Accept' button
 *  7.  Clicking Accept calls acceptVaultGrant with the correct grantId
 *  8.  Clicking own-vault entry sets activeVaultOwnerId to null (own vault)
 *  9.  Clicking a shared vault entry sets activeVaultOwnerId to the owner id
 *  10. Dropdown closes after a vault is selected
 */

import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import React from 'react';
import { useVaultStore } from '../../store/useVaultStore';

// ── Mocks ─────────────────────────────────────────────────────────────────
// NOTE: vi.mock is hoisted to the top of the file by Vitest, so the factory
// must NOT reference any const/let declared in module scope — that would be a
// TDZ crash.  Return plain vi.fn() stubs here; wire up return values in
// beforeEach instead.
vi.mock('../../services/vaultApi', () => ({
  fetchMyVaultGrants: vi.fn(),
  acceptVaultGrant: vi.fn(),
}));

import { fetchMyVaultGrants, acceptVaultGrant } from '../../services/vaultApi';
import VaultSwitcher from '../VaultSwitcher';

const mockGrants = [
  { grantId: null, ownerId: 1, label: 'My Notes', permission: 'owner', pending: false },
  { grantId: 7, ownerId: 9, label: "Alice's Vault", permission: 'read', pending: false },
  { grantId: 8, ownerId: 10, label: "Bob's Vault", permission: 'read', pending: true },
];

function renderSwitcher() {
  return render(
    <MemoryRouter>
      <VaultSwitcher />
    </MemoryRouter>,
  );
}

beforeEach(() => {
  (fetchMyVaultGrants as ReturnType<typeof vi.fn>).mockResolvedValue(mockGrants);
  (acceptVaultGrant as ReturnType<typeof vi.fn>).mockResolvedValue({});
  useVaultStore.setState({ activeVaultOwnerId: null });
  vi.clearAllMocks();
});
afterEach(() => { vi.restoreAllMocks(); });

describe('VaultSwitcher', () => {
  it('renders the switcher trigger button', () => {
    renderSwitcher();
    expect(screen.getByRole('button', { name: /vault/i })).toBeInTheDocument();
  });

  it('dropdown is closed by default', () => {
    renderSwitcher();
    expect(screen.queryByText("Alice's Vault")).not.toBeInTheDocument();
  });

  it('clicking trigger opens the dropdown', async () => {
    renderSwitcher();
    fireEvent.click(screen.getByRole('button', { name: /vault/i }));
    await waitFor(() => expect(screen.getByText("Alice's Vault")).toBeInTheDocument());
  });

  it('own-vault entry is shown with You badge', async () => {
    renderSwitcher();
    fireEvent.click(screen.getByRole('button', { name: /vault/i }));
    await waitFor(() => expect(screen.getByText('My Notes')).toBeInTheDocument());
    // The component renders a "You" badge on the own-vault row (not "owner")
    expect(screen.getByText('You')).toBeInTheDocument();
  });

  it('shared vault entries are listed', async () => {
    renderSwitcher();
    fireEvent.click(screen.getByRole('button', { name: /vault/i }));
    await waitFor(() => {
      expect(screen.getByText("Alice's Vault")).toBeInTheDocument();
      expect(screen.getByText("Bob's Vault")).toBeInTheDocument();
    });
  });

  it('pending grant shows an Accept button', async () => {
    renderSwitcher();
    fireEvent.click(screen.getByRole('button', { name: /vault/i }));
    await waitFor(() => expect(screen.getByRole('button', { name: /accept/i })).toBeInTheDocument());
  });

  it('clicking Accept calls acceptVaultGrant with correct grantId', async () => {
    renderSwitcher();
    fireEvent.click(screen.getByRole('button', { name: /vault/i }));
    await waitFor(() => screen.getByRole('button', { name: /accept/i }));
    fireEvent.click(screen.getByRole('button', { name: /accept/i }));
    await waitFor(() => expect(acceptVaultGrant).toHaveBeenCalledWith(8));
  });

  it('clicking own-vault sets activeVaultOwnerId to null', async () => {
    // Start in a foreign vault
    useVaultStore.setState({ activeVaultOwnerId: 9 });
    renderSwitcher();
    fireEvent.click(screen.getByRole('button', { name: /vault/i }));
    await waitFor(() => screen.getByText('My Notes'));
    fireEvent.click(screen.getByText('My Notes'));
    await waitFor(() => expect(useVaultStore.getState().activeVaultOwnerId).toBeNull());
  });

  it('clicking shared vault sets activeVaultOwnerId', async () => {
    renderSwitcher();
    fireEvent.click(screen.getByRole('button', { name: /vault/i }));
    await waitFor(() => screen.getByText("Alice's Vault"));
    fireEvent.click(screen.getByText("Alice's Vault"));
    await waitFor(() => expect(useVaultStore.getState().activeVaultOwnerId).toBe(9));
  });

  it('dropdown closes after a vault is selected', async () => {
    renderSwitcher();
    fireEvent.click(screen.getByRole('button', { name: /vault/i }));
    await waitFor(() => screen.getByText("Alice's Vault"));
    fireEvent.click(screen.getByText("Alice's Vault"));
    await waitFor(() => expect(screen.queryByText("Alice's Vault")).not.toBeInTheDocument());
  });
});
