/**
 * appStore.ts — re-export shim.
 * Legacy components import from './appStore'; the canonical store
 * is useAppStore.ts. This file simply re-exports everything so both
 * import paths work without touching consumer files.
 */
export { useAppStore, type AppState, type AppStore } from './useAppStore';
