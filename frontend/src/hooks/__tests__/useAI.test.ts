import { describe, it, expect, vi } from 'vitest';
import { renderHook, waitFor, act } from '@testing-library/react';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { createElement } from 'react';

vi.mock('../../api/ai', () => ({
  chatQuery:       vi.fn(async () => ({ answer: 'The Dharma is clear.', sources: ['note-001'], mode: 'hybrid' })),
  getLinkSuggestions: vi.fn(async () => [
    { target_note_id: 'note-002', target_title: 'Dependent Origination', reason: 'Related concept', score: 0.91 },
  ]),
  critiqueNote:    vi.fn(async () => ({
    note_id: 'note-001', atomicity_score: 8, atomicity_feedback: 'Good.',
    connectivity_score: 7, connectivity_feedback: 'Add more links.',
    standalone_score: 9, standalone_feedback: 'Clear.',
    insight_score: 8, insight_feedback: 'Insightful.', overall_feedback: 'Strong note.',
  })),
}));

import { useAIChat, useLinkSuggestions, useCritiqueNote } from '../useAI';

function makeWrapper() {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return ({ children }: { children: React.ReactNode }) =>
    createElement(QueryClientProvider, { client: qc }, children);
}

describe('useAIChat', () => {
  it('mutation resolves with answer', async () => {
    const { result } = renderHook(() => useAIChat(), { wrapper: makeWrapper() });
    await act(async () => {
      await result.current.mutateAsync({ query: 'What is sunyata?', mode: 'hybrid' });
    });
    expect(result.current.data?.answer).toBe('The Dharma is clear.');
  });
});

describe('useLinkSuggestions', () => {
  it('returns suggestions for a note', async () => {
    const { result } = renderHook(() => useLinkSuggestions('note-001'), { wrapper: makeWrapper() });
    await waitFor(() => expect(result.current.isSuccess).toBe(true));
    expect(result.current.data?.[0].target_title).toBe('Dependent Origination');
  });
});

describe('useCritiqueNote', () => {
  it('mutation resolves with critique', async () => {
    const { result } = renderHook(() => useCritiqueNote(), { wrapper: makeWrapper() });
    await act(async () => {
      await result.current.mutateAsync('note-001');
    });
    expect(result.current.data?.overall_feedback).toBe('Strong note.');
  });
});
