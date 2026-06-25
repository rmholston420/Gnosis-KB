/**
 * WikilinkAutocomplete editor test
 *
 * vi.mock() path must be the RELATIVE path that Vitest resolves from this
 * test file — NOT the '@/' alias form.  Vitest does not apply Vite path
 * aliases inside vi.mock() module-ID strings, so '@/services/api' is treated
 * as a bare package name rather than resolving to src/services/api.  The mock
 * would be silently skipped, the real module would load, and WikilinkAutocomplete
 * would call useQuery without a QueryClientProvider, crashing the test.
 *
 * Relative path from this file:
 *   src/components/editor/__tests__/  →  ../../../services/api
 */
import React from 'react';
import { render } from '@testing-library/react';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { describe, it, expect, vi, beforeEach } from 'vitest';

vi.mock('../../../services/api', () => ({
  default: { listNotes: vi.fn().mockResolvedValue({ items: [] }) },
}));

import WikilinkAutocomplete from '../WikilinkAutocomplete';

describe('editor WikilinkAutocomplete', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('renders nothing without anchorRect', () => {
    const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } });
    const { container } = render(
      <QueryClientProvider client={queryClient}>
        <WikilinkAutocomplete query="a" anchorRect={null} onSelect={vi.fn()} onClose={vi.fn()} />
      </QueryClientProvider>,
    );
    expect(container).toBeTruthy();
  });
});
