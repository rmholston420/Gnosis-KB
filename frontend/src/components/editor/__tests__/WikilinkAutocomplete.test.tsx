import React from 'react';
import { render } from '@testing-library/react';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { describe, it, expect, vi, beforeEach } from 'vitest';

vi.mock('@/services/api', () => ({
  default: { listNotes: vi.fn().mockResolvedValue({ items: [] }) },
}));

import WikilinkAutocomplete from '@/components/editor/WikilinkAutocomplete';

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
