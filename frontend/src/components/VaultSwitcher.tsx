/**
 * VaultSwitcher — sidebar popover for switching between own vault and
 * shared vaults the user has been granted access to.
 *
 * Layout in the sidebar:
 *   [ vault icon button ]  ← always visible; shows active-vault indicator
 *        ↓ click
 *   ┌──────────────────────────────┐
 *   │  MY VAULT                    │
 *   │  ● Ryan's KB          (You)  │  ← active = filled circle + teal ring
 *   ├──────────────────────────────┤
 *   │  SHARED WITH ME              │
 *   │  ○ Alice's KB        [read]  │
 *   │  ○ Team Vault       [write]  │
 *   ├──────────────────────────────┤
 *   │  PENDING INVITES             │
 *   │  ○ Bob's KB       [Accept]   │
 *   └──────────────────────────────┘
 *
 * When a non-own vault is active a slim teal banner is rendered at the very
 * top of the main content area (outside this component — App.tsx renders it)
 * reading "Viewing: Alice's KB  [Return to my vault ×]"
 */

import React, { useEffect, useRef, useState, useCallback } from 'react';
import { Vault, CheckCircle, Circle, Loader2 } from 'lucide-react';
import { useVaultStore } from '../store/useVaultStore';
import type { VaultGrant } from '../services/vaultApi';

// ---------------------------------------------------------------------------
// Permission chip
// ---------------------------------------------------------------------------
function PermChip({ perm }: { perm: 'owner' | 'read' | 'write' }) {
  if (perm === 'owner')
    return (
      <span className="rounded-full bg-blue-100 px-2 py-0.5 text-xs font-medium text-blue-700 dark:bg-blue-900/40 dark:text-blue-300">
        You
      </span>
    );
  if (perm === 'write')
    return (
      <span className="rounded-full bg-emerald-100 px-2 py-0.5 text-xs font-medium text-emerald-700 dark:bg-emerald-900/40 dark:text-emerald-300">
        write
      </span>
    );
  return (
    <span className="rounded-full bg-gray-100 px-2 py-0.5 text-xs font-medium text-gray-600 dark:bg-gray-800 dark:text-gray-400">
      read
    </span>
  );
}

// ---------------------------------------------------------------------------
// Grant row
// ---------------------------------------------------------------------------
function GrantRow({
  grant,
  isActive,
  onSelect,
  onAccept,
}: {
  grant: VaultGrant;
  isActive: boolean;
  onSelect: (g: VaultGrant) => void;
  onAccept: (grantId: number) => void;
}) {
  const [accepting, setAccepting] = useState(false);

  const handleAccept = async (e: React.MouseEvent | React.KeyboardEvent) => {
    e.stopPropagation();
    if (grant.grantId === null) return;
    setAccepting(true);
    try {
      await onAccept(grant.grantId);
    } finally {
      setAccepting(false);
    }
  };

  return (
    <button
      role="option"
      aria-selected={isActive}
      disabled={grant.pending}
      onClick={() => !grant.pending && onSelect(grant)}
      className={`flex w-full items-center gap-2 rounded-md px-3 py-2 text-left text-sm transition-colors
        ${
          grant.pending
            ? 'cursor-default opacity-60'
            : isActive
            ? 'bg-teal-50 text-teal-800 dark:bg-teal-900/30 dark:text-teal-200'
            : 'hover:bg-gray-100 dark:hover:bg-gray-800'
        }`}
    >
      {/* Active indicator */}
      {isActive ? (
        <CheckCircle size={14} className="shrink-0 text-teal-600 dark:text-teal-400" />
      ) : (
        <Circle size={14} className="shrink-0 text-gray-300 dark:text-gray-600" />
      )}

      {/* Label */}
      <span className="min-w-0 flex-1 truncate font-medium">{grant.label}</span>

      {/* Right slot: accept control (not a <button> — we're already inside one)
          or permission chip */}
      {grant.pending ? (
        <span
          role="button"
          aria-label="Accept"
          aria-disabled={accepting}
          tabIndex={accepting ? -1 : 0}
          onClick={handleAccept}
          onKeyDown={(e) => {
            if (e.key === 'Enter' || e.key === ' ') {
              e.preventDefault();
              handleAccept(e);
            }
          }}
          className="ml-auto flex shrink-0 cursor-pointer items-center gap-1 rounded bg-teal-600 px-2 py-0.5 text-xs font-semibold text-white hover:bg-teal-700 aria-disabled:opacity-60"
        >
          {accepting && <Loader2 size={10} className="animate-spin" />}
          Accept
        </span>
      ) : (
        <PermChip perm={grant.permission} />
      )}
    </button>
  );
}

// ---------------------------------------------------------------------------
// Section heading
// ---------------------------------------------------------------------------
function SectionLabel({ children }: { children: React.ReactNode }) {
  return (
    <p className="mb-1 mt-3 px-3 text-xs font-semibold uppercase tracking-widest text-gray-400 dark:text-gray-500 first:mt-0">
      {children}
    </p>
  );
}

// ---------------------------------------------------------------------------
// Main component
// ---------------------------------------------------------------------------
export default function VaultSwitcher() {
  const [open, setOpen] = useState(false);
  const buttonRef = useRef<HTMLButtonElement>(null);
  const panelRef = useRef<HTMLDivElement>(null);

  const { grants, loading, activeVaultOwnerId, fetchGrants, switchVault, acceptInvite } =
    useVaultStore();

  // Fetch grants on mount and when popover opens
  useEffect(() => {
    fetchGrants();
  }, [fetchGrants]);

  // Close on outside click
  useEffect(() => {
    if (!open) return;
    const handler = (e: MouseEvent) => {
      if (
        !buttonRef.current?.contains(e.target as Node) &&
        !panelRef.current?.contains(e.target as Node)
      ) {
        setOpen(false);
      }
    };
    document.addEventListener('mousedown', handler);
    return () => document.removeEventListener('mousedown', handler);
  }, [open]);

  // Close on Escape
  useEffect(() => {
    if (!open) return;
    const handler = (e: KeyboardEvent) => {
      if (e.key === 'Escape') {
        setOpen(false);
        buttonRef.current?.focus();
      }
    };
    document.addEventListener('keydown', handler);
    return () => document.removeEventListener('keydown', handler);
  }, [open]);

  const handleSelect = useCallback(
    (grant: VaultGrant) => {
      switchVault(
        grant.permission === 'owner' ? null : grant.ownerId,
        grant.label
      );
      setOpen(false);
    },
    [switchVault]
  );

  const handleAccept = useCallback(
    async (grantId: number) => {
      await acceptInvite(grantId);
    },
    [acceptInvite]
  );

  const isVaultActive = (grant: VaultGrant) => {
    if (grant.permission === 'owner') return activeVaultOwnerId === null;
    return activeVaultOwnerId === grant.ownerId;
  };

  const ownVault = grants.find((g) => g.permission === 'owner');
  const sharedVaults = grants.filter((g) => g.permission !== 'owner' && !g.pending);
  const pendingVaults = grants.filter((g) => g.pending);
  const hasSharedOrPending = sharedVaults.length > 0 || pendingVaults.length > 0;
  const isViewingForeign = activeVaultOwnerId !== null;

  return (
    <div className="relative">
      {/* Trigger button */}
      <button
        ref={buttonRef}
        aria-label="Switch vault"
        aria-haspopup="listbox"
        aria-expanded={open}
        onClick={() => setOpen((v) => !v)}
        className={`relative flex h-10 w-10 items-center justify-center rounded-lg transition-colors
          ${
            open
              ? 'bg-teal-100 text-teal-700 dark:bg-teal-900/40 dark:text-teal-300'
              : isViewingForeign
              ? 'text-teal-600 dark:text-teal-400'
              : 'text-gray-500 hover:bg-gray-100 dark:hover:bg-gray-800'
          }`}
      >
        <Vault size={20} />
        {/* Active-foreign dot */}
        {isViewingForeign && (
          <span
            aria-hidden
            className="absolute -right-0.5 -top-0.5 h-2.5 w-2.5 rounded-full border-2 border-white bg-teal-500 dark:border-gray-950"
          />
        )}
        {/* Pending invite badge */}
        {!isViewingForeign && pendingVaults.length > 0 && (
          <span
            aria-label={`${pendingVaults.length} pending vault invite${pendingVaults.length > 1 ? 's' : ''}`}
            className="absolute -right-0.5 -top-0.5 flex h-4 w-4 items-center justify-center rounded-full border-2 border-white bg-amber-500 text-[9px] font-bold text-white dark:border-gray-950"
          >
            {pendingVaults.length}
          </span>
        )}
      </button>

      {/* Dropdown panel */}
      {open && (
        <div
          ref={panelRef}
          role="listbox"
          aria-label="Available vaults"
          className="
            absolute left-12 top-0 z-50 min-w-[220px] rounded-xl border border-gray-200
            bg-white p-2 shadow-xl dark:border-gray-700 dark:bg-gray-900
          "
        >
          {loading && grants.length === 0 ? (
            <div className="flex items-center justify-center py-6">
              <Loader2 size={18} className="animate-spin text-gray-400" />
            </div>
          ) : (
            <>
              {/* Own vault */}
              {ownVault && (
                <>
                  <SectionLabel>My vault</SectionLabel>
                  <GrantRow
                    grant={ownVault}
                    isActive={isVaultActive(ownVault)}
                    onSelect={handleSelect}
                    onAccept={handleAccept}
                  />
                </>
              )}

              {/* Shared vaults */}
              {sharedVaults.length > 0 && (
                <>
                  <SectionLabel>Shared with me</SectionLabel>
                  {sharedVaults.map((g) => (
                    <GrantRow
                      key={g.ownerId}
                      grant={g}
                      isActive={isVaultActive(g)}
                      onSelect={handleSelect}
                      onAccept={handleAccept}
                    />
                  ))}
                </>
              )}

              {/* Pending invites */}
              {pendingVaults.length > 0 && (
                <>
                  <SectionLabel>Pending invites</SectionLabel>
                  {pendingVaults.map((g) => (
                    <GrantRow
                      key={g.grantId}
                      grant={g}
                      isActive={false}
                      onSelect={handleSelect}
                      onAccept={handleAccept}
                    />
                  ))}
                </>
              )}

              {/* Empty state: only own vault, no shares */}
              {!hasSharedOrPending && (
                <p className="mt-2 px-3 pb-2 text-xs text-gray-400 dark:text-gray-500">
                  No shared vaults yet. Invite someone in Settings → Vault Sharing.
                </p>
              )}
            </>
          )}
        </div>
      )}
    </div>
  );
}

// ---------------------------------------------------------------------------
// Vault context banner (exported separately — rendered by App.tsx)
// ---------------------------------------------------------------------------
export function VaultContextBanner() {
  const { activeVaultOwnerId, activeVaultLabel, resetToOwnVault } = useVaultStore();

  if (activeVaultOwnerId === null) return null;

  return (
    <div
      role="status"
      aria-live="polite"
      className="flex items-center justify-between gap-2 border-b border-teal-200 bg-teal-50 px-4 py-1.5 text-xs text-teal-800 dark:border-teal-800/50 dark:bg-teal-950/40 dark:text-teal-300"
    >
      <span>
        <span className="font-semibold">Viewing:</span> {activeVaultLabel}
      </span>
      <button
        onClick={resetToOwnVault}
        className="flex items-center gap-1 rounded px-2 py-0.5 font-medium hover:bg-teal-100 dark:hover:bg-teal-900/40"
        aria-label="Return to my vault"
      >
        Return to my vault
        <span aria-hidden>×</span>
      </button>
    </div>
  );
}
