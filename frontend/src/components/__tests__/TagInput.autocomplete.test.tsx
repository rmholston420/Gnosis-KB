/**
 * TagInput.autocomplete.test.tsx
 * TagInput uses useQuery internally — must be wrapped in QueryClientProvider.
 */
import React from 'react';
import { render, screen } from '@testing-library/react';
import { describe, it, expect, vi, beforeEach } from 'vitest';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import TagInput from '@/components/TagInput';

const mockListTags = vi.fn();
vi.mock('@/services/api', () => ({
  default: { listTags: (...a: unknown[]) => mockListTags(...a) },
}));

function makeClient() {
  return new QueryClient({ defaultOptions: { queries: { retry: false } } });
}

beforeEach(() => {
  mockListTags.mockResolvedValue([]);
});

describe('TagInput.autocomplete', () => {
  it('renders input', () => {
    render(
      <QueryClientProvider client={makeClient()}>
        <TagInput tags={[]} onChange={vi.fn()} />
      </QueryClientProvider>
    );
    expect(screen.getByRole('textbox')).toBeInTheDocument();
  });
});
