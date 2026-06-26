/**
 * store/vaultStore.ts — DEPRECATED.
 *
 * This file previously contained a duplicate Zustand store for vault/sync
 * state. It has been superseded by useVaultStore.ts which handles both
 * vault-owner context (shared vaults) and is the single authoritative vault
 * store consumed by api.ts and all components.
 *
 * Re-exports from useVaultStore.ts for backwards compatibility so any
 * accidental imports of this file continue to reference the correct store
 * instead of creating a second, un-persisted instance.
 *
 * TODO: Remove all imports of this file and delete it in a future cleanup.
 */
export { useVaultStore as default, useVaultStore } from './useVaultStore';
