/**
 * CommandPalette — re-export barrel
 * ==================================
 * The canonical CommandPalette lives in components/search/CommandPalette.tsx.
 * This file re-exports it at the legacy path so both import locations work:
 *
 *   import CommandPalette from '@/components/CommandPalette'           ← this file
 *   import CommandPalette from '@/components/search/CommandPalette'    ← canonical
 *
 * Tests that import from the top-level path (e.g. CommandPalette.test.tsx
 * in components/__tests__/) will resolve to the same component instance.
 */
export { default } from './search/CommandPalette';
