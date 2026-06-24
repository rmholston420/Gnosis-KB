/**
 * AiSidebar.test.tsx
 * Tests:
 *  - tabs render: Summary, Links, Tags, Critique
 *  - clicking a tab shows the correct panel
 *  - Generate Summary button fires mutation when noteId provided
 *  - noteId=null shows disabled / prompt state
 *  - onInsertLink callback is called when a link suggestion is accepted
 */
import React from 'react';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { MemoryRouter } from 'react-router-dom';
import { AiSidebar } from '../AiSidebar';
import * as aiApi from '../../../api/ai';
import type { LinkSuggestion } from '../../../types';

const linkFixture: LinkSuggestion[] = [
  { source_id: 'a', target_id: 'b', target_title: 'Four Noble Truths', reason: 'Core teaching', score: 0.92 },
];

function makeClient() {
  return new QueryClient({ defaultOptions: { queries: { retry: false }, mutations: { retry: false } } });
}

function Wrapper({ children }: { children: React.ReactNode }) {
  return (
    <QueryClientProvider client={makeClient()}>
      <MemoryRouter>{children}</MemoryRouter>
    </QueryClientProvider>
  );
}

describe('AiSidebar', () => {
  afterEach(() => vi.restoreAllMocks());

  it('renders all four tab buttons', () => {
    render(<Wrapper><AiSidebar noteId={null} onInsertLink={() => {}} onInsertTag={() => {}} /></Wrapper>);
    expect(screen.getByRole('tab', { name: /summary/i })).toBeInTheDocument();
    expect(screen.getByRole('tab', { name: /links/i })).toBeInTheDocument();
    expect(screen.getByRole('tab', { name: /tags/i })).toBeInTheDocument();
    expect(screen.getByRole('tab', { name: /critique/i })).toBeInTheDocument();
  });

  it('shows prompts user to open a note when noteId is null', () => {
    render(<Wrapper><AiSidebar noteId={null} onInsertLink={() => {}} onInsertTag={() => {}} /></Wrapper>);
    expect(screen.getByText(/open a note/i)).toBeInTheDocument();
  });

  it('switches to Links tab and calls onInsertLink when suggestion accepted', async () => {
    vi.spyOn(aiApi, 'fetchLinkSuggestions').mockResolvedValue(linkFixture);
    const onInsertLink = vi.fn();
    render(
      <Wrapper>
        <AiSidebar noteId="note-123" onInsertLink={onInsertLink} onInsertTag={() => {}} />
      </Wrapper>,
    );
    fireEvent.click(screen.getByRole('tab', { name: /links/i }));
    await waitFor(() => screen.getByText('Four Noble Truths'));
    fireEvent.click(screen.getByRole('button', { name: /insert/i }));
    expect(onInsertLink).toHaveBeenCalledWith(linkFixture[0]);
  });

  it('generate summary button fires summarize mutation', async () => {
    const spy = vi.spyOn(aiApi, 'generateSummary').mockResolvedValue({ summary: 'A summary.' });
    render(<Wrapper><AiSidebar noteId="note-456" onInsertLink={() => {}} onInsertTag={() => {}} /></Wrapper>);
    const generateBtn = screen.getByRole('button', { name: /generate summary/i });
    fireEvent.click(generateBtn);
    await waitFor(() => expect(spy).toHaveBeenCalledWith('note-456'));
  });
});
