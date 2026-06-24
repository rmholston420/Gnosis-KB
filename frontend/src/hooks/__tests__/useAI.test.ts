/// <reference types="vitest/globals" />
import { renderHook, waitFor } from '@testing-library/react';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import React from 'react';
import { useAIChat, useCritiqueNote, useNoteSummary } from '../useAI';

const mockCritiqueNote  = vi.fn();
const mockSummarizeNote = vi.fn();
const mockStreamQuery   = vi.fn();

vi.mock('../../services/api', () => ({
  default: {
    critiqueNote:  (...a: unknown[]) => mockCritiqueNote(...a),
    summarizeNote: (...a: unknown[]) => mockSummarizeNote(...a),
    streamQuery:   (...a: unknown[]) => mockStreamQuery(...a),
  },
}));

const wrapper = ({ children }: { children: React.ReactNode }) =>
  React.createElement(
    QueryClientProvider,
    { client: new QueryClient({ defaultOptions: { queries: { retry: false } } }) },
    children,
  );

describe('useAI hooks', () => {
  beforeEach(() => { vi.clearAllMocks(); });

  it('useAIChat is a mutation hook', () => {
    mockStreamQuery.mockReturnValue({ addEventListener: vi.fn(), close: vi.fn() });
    const { result } = renderHook(() => useAIChat(), { wrapper });
    expect(typeof result.current.mutateAsync).toBe('function');
  });

  it('useCritiqueNote / alias fetches critique', async () => {
    mockCritiqueNote.mockResolvedValue({
      critique: 'Needs more citations',
      suggestions: [],
    });
    const { result } = renderHook(() => useCritiqueNote('note-001'), { wrapper });
    await waitFor(() => result.current.isSuccess);
    expect(result.current.data?.critique).toBe('Needs more citations');
  });

  it('useNoteSummary fetches summary', async () => {
    mockSummarizeNote.mockResolvedValue({
      summary: 'A short note about impermanence.',
      keywords: ['impermanence'],
    });
    const { result } = renderHook(() => useNoteSummary('note-002'), { wrapper });
    await waitFor(() => result.current.isSuccess);
    expect(result.current.data?.summary).toContain('impermanence');
  });
});
