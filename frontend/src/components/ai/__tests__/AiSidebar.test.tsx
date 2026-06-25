/**
 * AiSidebar.test.tsx
 */
import React from 'react';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { MemoryRouter } from 'react-router-dom';
import { vi, describe, it, expect, beforeEach } from 'vitest';
import { AiSidebar } from '../AiSidebar';
import type { LinkSuggestResult, SummarizeResult } from '../../../api/ai';

const linkFixture: LinkSuggestResult = {
  suggestions: [
    { target_note_id: 'n1', target_title: 'Emptiness', score: 0.95, reason: 'Related concept' },
  ],
};

const mockSuggestLinks = vi.fn();
const mockSuggestTags = vi.fn();
const mockSummarizeNote = vi.fn();
const mockCritiqueNote = vi.fn();
const mockOrphanAudit = vi.fn();

vi.mock('../../../api/ai', () => ({
  suggestLinks: (...a: unknown[]) => mockSuggestLinks(...a),
  suggestTags: (...a: unknown[]) => mockSuggestTags(...a),
  summarizeNote: (...a: unknown[]) => mockSummarizeNote(...a),
  critiqueNote: (...a: unknown[]) => mockCritiqueNote(...a),
  orphanAudit: (...a: unknown[]) => mockOrphanAudit(...a),
  streamingChatUrl: vi.fn(() => ''),
  chat: vi.fn(),
  aiApi: {
    suggestLinks: (...a: unknown[]) => mockSuggestLinks(...a),
    suggestTags: (...a: unknown[]) => mockSuggestTags(...a),
    summarizeNote: (...a: unknown[]) => mockSummarizeNote(...a),
    critiqueNote: (...a: unknown[]) => mockCritiqueNote(...a),
  },
}));

function Wrapper({ children }: { children: React.ReactNode }) {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return (
    <QueryClientProvider client={qc}>
      <MemoryRouter>{children}</MemoryRouter>
    </QueryClientProvider>
  );
}

describe('AiSidebar', () => {
  beforeEach(() => {
    mockSuggestLinks.mockReset();
    mockSuggestTags.mockReset();
    mockSummarizeNote.mockReset();
    mockCritiqueNote.mockReset();
    mockSuggestLinks.mockResolvedValue({ suggestions: [] });
    mockSuggestTags.mockResolvedValue({ suggestions: [] });
  });

  it('renders the empty guard when noteId is null', () => {
    render(
      <Wrapper>
        <AiSidebar noteId={null} onInsertLink={() => {}} onInsertTag={() => {}} />
      </Wrapper>,
    );
    expect(screen.getByText(/open a note/i)).toBeInTheDocument();
  });

  it('renders all four section headers when a note is open', () => {
    render(
      <Wrapper>
        <AiSidebar noteId="note-456" onInsertLink={() => {}} onInsertTag={() => {}} />
      </Wrapper>,
    );
    expect(screen.getByText(/AI Summary/i)).toBeInTheDocument();
    expect(screen.getByText(/Suggested Links/i)).toBeInTheDocument();
    expect(screen.getByText(/Suggested Tags/i)).toBeInTheDocument();
    expect(screen.getByText(/ZK Critique/i)).toBeInTheDocument();
  });

  it('accepts a link suggestion and calls onInsertLink', async () => {
    mockSuggestLinks.mockResolvedValue(linkFixture);
    const onInsertLink = vi.fn();
    render(
      <Wrapper>
        <AiSidebar noteId="note-456" onInsertLink={onInsertLink} onInsertTag={() => {}} />
      </Wrapper>,
    );
    fireEvent.click(screen.getByText(/Suggested Links/i));
    await waitFor(() => screen.getByText('Emptiness'));
    fireEvent.click(screen.getByRole('button', { name: /insert/i }));
    expect(onInsertLink).toHaveBeenCalledWith(linkFixture.suggestions[0]);
  });

  it('generate summary button fires summarize mutation', async () => {
    const mockResult: SummarizeResult = { summary: 'A summary.' };
    mockSummarizeNote.mockResolvedValue(mockResult);
    render(
      <Wrapper>
        <AiSidebar noteId="note-456" onInsertLink={() => {}} onInsertTag={() => {}} />
      </Wrapper>,
    );
    fireEvent.click(screen.getByText(/AI Summary/i));
    const generateBtn = screen.getByRole('button', { name: /generate summary/i });
    fireEvent.click(generateBtn);
    await waitFor(() => expect(mockSummarizeNote).toHaveBeenCalledWith('note-456'));
    await waitFor(() => screen.getByText('A summary.'));
  });
});
