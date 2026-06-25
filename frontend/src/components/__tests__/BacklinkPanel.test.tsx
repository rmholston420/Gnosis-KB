/**
 * BacklinkPanel.test.tsx — smoke test for BacklinksPanel component.
 */
import React from 'react';
import { render, screen } from '@testing-library/react';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { BacklinksPanel } from '../editor/BacklinksPanel';
import type { LinkRef } from '../../types';

function makeLinkRef(sourceId: string, targetId: string): LinkRef {
  return {
    note_id:   sourceId,
    title:     '',
    source_id: sourceId,
    target_id: targetId,
    context:   '',
    link_text: '',
    link_type: 'wikilink',
  };
}

const wrapper = ({ children }: { children: React.ReactNode }) => (
  <QueryClientProvider client={new QueryClient({ defaultOptions: { queries: { retry: false } } })}>
    {children}
  </QueryClientProvider>
);

describe('BacklinksPanel', () => {
  it('renders empty state when noteId is null', () => {
    render(<BacklinksPanel noteId={null} />, { wrapper });
    expect(screen.getByText(/no note selected/i)).toBeInTheDocument();
  });

  it('renders loading state with a valid noteId', () => {
    render(<BacklinksPanel noteId="note-1" />, { wrapper });
    expect(screen.getByText(/loading/i)).toBeInTheDocument();
  });

  it('makeLinkRef returns a valid LinkRef shape', () => {
    const ref = makeLinkRef('a', 'b');
    expect(ref.note_id).toBe('a');
    expect(ref.title).toBe('');
  });
});
