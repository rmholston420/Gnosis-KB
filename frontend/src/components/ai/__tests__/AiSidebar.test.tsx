/**
 * AiSidebar.test.tsx
 * Spy on real exports: suggestLinks, summarizeNote.
 * Render with noteId='note-456' so the tabs are shown (not the guard).
 */
import React from 'react';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { MemoryRouter } from 'react-router-dom';
import { vi, describe, it, expect, beforeEach } from 'vitest';
import * as aiApi from '../../../api/ai';
import { AiSidebar } from '../AiSidebar';

const linkFixture = [
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

  it('renders all four tab buttons when a note is open', () => {
    render(
      <Wrapper>
        <AiSidebar noteId="note-456" onInsertLink={() => {}} onInsertTag={() => {}} />
      </Wrapper>
    );
    expect(screen.getByRole('tab', { name: /summary/i })).toBeInTheDocument();
    expect(screen.getByRole('tab', { name: /links/i })).toBeInTheDocument();
    expect(screen.getByRole('tab', { name: /tags/i })).toBeInTheDocument();
    expect(screen.getByRole('tab', { name: /critique/i })).toBeInTheDocument();
  });

  it('switches to Links tab and calls onInsertLink when suggestion accepted', async () => {
    vi.spyOn(aiApi, 'suggestLinks').mockResolvedValue(linkFixture);
    const onInsertLink = vi.fn();
    render(
      <Wrapper>
        <AiSidebar noteId="note-456" onInsertLink={onInsertLink} onInsertTag={() => {}} />
      </Wrapper>
    );
    fireEvent.click(screen.getByRole('tab', { name: /links/i }));
    fireEvent.click(screen.getByRole('button', { name: /fetch link suggestions/i }));
    await waitFor(() => screen.getByText('Emptiness'));
    fireEvent.click(screen.getByRole('button', { name: /accept/i }));
    expect(onInsertLink).toHaveBeenCalledWith('Emptiness');
  });

  it('generate summary button fires summarize mutation', async () => {
    const spy = vi.spyOn(aiApi, 'summarizeNote').mockResolvedValue({ summary: 'A summary.' });
    render(
      <Wrapper>
        <AiSidebar noteId="note-456" onInsertLink={() => {}} onInsertTag={() => {}} />
      </Wrapper>
    );
    const generateBtn = screen.getByRole('button', { name: /generate summary/i });
    fireEvent.click(generateBtn);
    await waitFor(() => expect(spy).toHaveBeenCalledWith('note-456'));
    await waitFor(() => screen.getByText('A summary.'));
  });
});
