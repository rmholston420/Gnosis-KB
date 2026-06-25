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

// These are plain variables that will be assigned below inside vi.mock.
// They are declared with let so the factory closure can reference them
// after the factory has already created the vi.fn() instances.
let mockSuggestLinks: ReturnType<typeof vi.fn>;
let mockSuggestTags: ReturnType<typeof vi.fn>;
let mockSummarizeNote: ReturnType<typeof vi.fn>;
let mockCritiqueNote: ReturnType<typeof vi.fn>;
let mockOrphanAudit: ReturnType<typeof vi.fn>;

// vi.mock is hoisted to the top of the file by Vitest's transformer.
// The factory must NOT reference variables declared with const/let outside
// the factory body that are only assigned AFTER the factory runs — that
// causes a TDZ (Temporal Dead Zone) ReferenceError.
//
// Safe pattern: create vi.fn() instances inline inside the factory, then
// assign them to the outer let variables so beforeEach / assertions can
// reference them.
vi.mock('../../../api/ai', () => {
  mockSuggestLinks  = vi.fn();
  mockSuggestTags   = vi.fn();
  mockSummarizeNote = vi.fn();
  mockCritiqueNote  = vi.fn();
  mockOrphanAudit   = vi.fn();

  return {
    suggestLinks:      (...a: unknown[]) => mockSuggestLinks(...a),
    suggestTags:       (...a: unknown[]) => mockSuggestTags(...a),
    summarizeNote:     (...a: unknown[]) => mockSummarizeNote(...a),
    critiqueNote:      (...a: unknown[]) => mockCritiqueNote(...a),
    orphanAudit:       (...a: unknown[]) => mockOrphanAudit(...a),
    streamingChatUrl:  vi.fn(() => ''),
    chat:              vi.fn(),
    getLinkSuggestions: vi.fn().mockResolvedValue([]),
    chatQuery:         vi.fn(),
    aiApi: {
      suggestLinks:  (...a: unknown[]) => mockSuggestLinks(...a),
      suggestTags:   (...a: unknown[]) => mockSuggestTags(...a),
      summarizeNote: (...a: unknown[]) => mockSummarizeNote(...a),
      critiqueNote:  (...a: unknown[]) => mockCritiqueNote(...a),
    },
  };
});

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
    expect(screen.getByText(/Zettelkasten Critique/i)).toBeInTheDocument();
  });

  it('shows link suggestions returned by suggestLinks', async () => {
    mockSuggestLinks.mockResolvedValue(linkFixture);
    render(
      <Wrapper>
        <AiSidebar noteId="note-123" onInsertLink={() => {}} onInsertTag={() => {}} />
      </Wrapper>,
    );
    await waitFor(() =>
      expect(screen.getByText('Emptiness')).toBeInTheDocument(),
    );
  });

  it('calls onInsertLink when a suggestion is clicked', async () => {
    mockSuggestLinks.mockResolvedValue(linkFixture);
    const onInsertLink = vi.fn();
    render(
      <Wrapper>
        <AiSidebar noteId="note-123" onInsertLink={onInsertLink} onInsertTag={() => {}} />
      </Wrapper>,
    );
    await waitFor(() => screen.getByText('Emptiness'));
    fireEvent.click(screen.getByText('Emptiness'));
    expect(onInsertLink).toHaveBeenCalledWith(
      expect.objectContaining({ target_note_id: 'n1' }),
    );
  });
});
