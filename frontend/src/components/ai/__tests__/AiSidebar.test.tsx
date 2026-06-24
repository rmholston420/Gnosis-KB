/**
 * AiSidebar.test.tsx
 *
 * The AiSidebar uses collapsible <Section> panels, not a tab-bar.
 * Each section header button has aria-expanded.  Spying on the api module
 * functions requires the query/mutation hooks to call the real api exports.
 *
 * onInsertLink receives the full LinkSuggestion object.
 */
import React from 'react';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { MemoryRouter } from 'react-router-dom';
import { vi, describe, it, expect, beforeEach } from 'vitest';
import * as aiApi from '../../../api/ai';
import { AiSidebar } from '../AiSidebar';
import type { LinkSuggestion } from '../../../types';

const linkFixture: LinkSuggestion[] = [
  { target_note_id: 'n1', target_title: 'Emptiness', score: 0.95, reason: 'Related concept' },
];

function Wrapper({ children }: { children: React.ReactNode }) {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return (
    <QueryClientProvider client={qc}>
      <MemoryRouter>{children}</MemoryRouter>
    </QueryClientProvider>
  );
}

describe('AiSidebar', () => {
  beforeEach(() => vi.restoreAllMocks());

  it('renders the empty guard when noteId is null', () => {
    render(
      <Wrapper>
        <AiSidebar noteId={null} onInsertLink={() => {}} onInsertTag={() => {}} />
      </Wrapper>
    );
    expect(screen.getByText(/open a note/i)).toBeInTheDocument();
  });

  it('renders all four section headers when a note is open', () => {
    render(
      <Wrapper>
        <AiSidebar noteId="note-456" onInsertLink={() => {}} onInsertTag={() => {}} />
      </Wrapper>
    );
    expect(screen.getByText(/AI Summary/i)).toBeInTheDocument();
    expect(screen.getByText(/Suggested Links/i)).toBeInTheDocument();
    expect(screen.getByText(/Suggested Tags/i)).toBeInTheDocument();
    expect(screen.getByText(/ZK Critique/i)).toBeInTheDocument();
  });

  it('accepts a link suggestion and calls onInsertLink', async () => {
    vi.spyOn(aiApi, 'suggestLinks').mockResolvedValue(linkFixture);
    const onInsertLink = vi.fn();
    render(
      <Wrapper>
        <AiSidebar noteId="note-456" onInsertLink={onInsertLink} onInsertTag={() => {}} />
      </Wrapper>
    );
    // Open the Suggested Links section
    fireEvent.click(screen.getByText(/Suggested Links/i));
    // Wait for the suggestion to appear after the query resolves
    await waitFor(() => screen.getByText('Emptiness'));
    fireEvent.click(screen.getByRole('button', { name: /insert/i }));
    expect(onInsertLink).toHaveBeenCalledWith(linkFixture[0]);
  });

  it('generate summary button fires summarize mutation', async () => {
    const spy = vi.spyOn(aiApi, 'summarizeNote').mockResolvedValue({ summary: 'A summary.' });
    render(
      <Wrapper>
        <AiSidebar noteId="note-456" onInsertLink={() => {}} onInsertTag={() => {}} />
      </Wrapper>
    );
    // Expand the AI Summary section (closed by default)
    fireEvent.click(screen.getByText(/AI Summary/i));
    const generateBtn = screen.getByRole('button', { name: /generate summary/i });
    fireEvent.click(generateBtn);
    await waitFor(() => expect(spy).toHaveBeenCalledWith('note-456'));
    await waitFor(() => screen.getByText('A summary.'));
  });
});
