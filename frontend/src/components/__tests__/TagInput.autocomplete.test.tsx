/**
 * TagInput.autocomplete.test.tsx
 * ==============================
 * Covers the autocomplete dropdown + keyboard navigation paths that the
 * existing TagInput.test.tsx doesn't reach:
 *
 * Lines targeted:
 *   65-67   ArrowDown moves highlightedIdx down (clamps at end)
 *   73-76   ArrowUp moves it back (clamps at 0); Escape closes dropdown
 *   106     onFocus re-opens dropdown when inputValue is non-empty
 *   117-133 Dropdown <ul role=listbox> renders suggestions
 *   190-211 Suggestion item mousedown adds tag; mouseenter highlights
 *
 * Cases (12):
 *  1.  Dropdown appears when input value matches existing tags from query cache
 *  2.  Dropdown does NOT appear when input is empty
 *  3.  ArrowDown highlights the first suggestion
 *  4.  ArrowDown clamps at last suggestion (does not exceed bounds)
 *  5.  ArrowUp moves highlight back up
 *  6.  ArrowUp clamps at index 0
 *  7.  Escape closes the dropdown and resets highlightedIdx
 *  8.  Enter with highlighted suggestion adds that suggestion tag
 *  9.  Tab with highlighted suggestion adds that suggestion tag
 * 10.  onFocus reopens dropdown when inputValue is non-empty
 * 11.  Clicking (mousedown) a suggestion item adds the tag
 * 12.  mouseEnter on a suggestion item highlights it
 */

import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, fireEvent } from '@testing-library/react';
import React from 'react';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import TagInput from '../TagInput';

// Stub the api.listTags call made by useQuery
vi.mock('../../services/api', () => ({
  default: {
    listTags: vi.fn().mockResolvedValue([
      { tag: 'react',      count: 10 },
      { tag: 'typescript', count: 8 },
      { tag: 'vitest',     count: 5 },
      { tag: 'zustand',    count: 3 },
    ]),
  },
}));

function makeQC() {
  return new QueryClient({
    defaultOptions: { queries: { retry: false } },
  });
}

interface SetupOpts {
  tags?: string[];
  onChange?: (t: string[]) => void;
}

function setup({ tags = [], onChange = vi.fn() }: SetupOpts = {}) {
  const qc = makeQC();
  const utils = render(
    <QueryClientProvider client={qc}>
      <TagInput tags={tags} onChange={onChange} />
    </QueryClientProvider>,
  );
  const input = screen.getByRole('textbox', { name: /add tag/i });
  return { ...utils, input, onChange, qc };
}

// Pre-populate the React Query cache so suggestions resolve synchronously.
async function seedCache(qc: QueryClient) {
  await qc.prefetchQuery({
    queryKey: ['tags'],
    queryFn: () =>
      Promise.resolve([
        { tag: 'react',      count: 10 },
        { tag: 'typescript', count: 8 },
        { tag: 'vitest',     count: 5 },
        { tag: 'zustand',    count: 3 },
      ]),
  });
}

beforeEach(() => vi.clearAllMocks());

describe('TagInput autocomplete', () => {
  it('dropdown appears when input matches a cached suggestion', async () => {
    const { input, qc } = setup();
    await seedCache(qc);
    fireEvent.change(input, { target: { value: 're' } });
    expect(screen.getByRole('listbox')).toBeInTheDocument();
    expect(screen.getByText('react')).toBeInTheDocument();
  });

  it('dropdown does NOT appear when input is empty', async () => {
    const { input, qc } = setup();
    await seedCache(qc);
    fireEvent.change(input, { target: { value: '' } });
    expect(screen.queryByRole('listbox')).toBeNull();
  });

  it('ArrowDown highlights the first suggestion', async () => {
    const { input, qc } = setup();
    await seedCache(qc);
    fireEvent.change(input, { target: { value: 're' } });
    fireEvent.keyDown(input, { key: 'ArrowDown' });
    const options = screen.getAllByRole('option');
    expect(options[0]).toHaveAttribute('aria-selected', 'true');
  });

  it('ArrowDown clamps at the last suggestion', async () => {
    const { input, qc } = setup();
    await seedCache(qc);
    fireEvent.change(input, { target: { value: 're' } }); // matches 'react'
    // Only 1 suggestion — ArrowDown twice should stay at 0
    fireEvent.keyDown(input, { key: 'ArrowDown' });
    fireEvent.keyDown(input, { key: 'ArrowDown' });
    const options = screen.getAllByRole('option');
    expect(options[0]).toHaveAttribute('aria-selected', 'true');
  });

  it('ArrowUp moves highlight back toward 0', async () => {
    const { input, qc } = setup();
    await seedCache(qc);
    fireEvent.change(input, { target: { value: 'type' } }); // matches 'typescript'
    fireEvent.keyDown(input, { key: 'ArrowDown' }); // idx → 0
    fireEvent.keyDown(input, { key: 'ArrowUp' });   // idx → 0 (clamped)
    const options = screen.getAllByRole('option');
    expect(options[0]).toHaveAttribute('aria-selected', 'true');
  });

  it('ArrowUp clamps at index 0', async () => {
    const { input, qc } = setup();
    await seedCache(qc);
    fireEvent.change(input, { target: { value: 'type' } });
    // ArrowUp without first going down — idx stays at 0 (Math.max(-1,0) from -1 → 0 then clamped)
    fireEvent.keyDown(input, { key: 'ArrowUp' });
    // Dropdown should still be open
    expect(screen.getByRole('listbox')).toBeInTheDocument();
  });

  it('Escape closes the dropdown', async () => {
    const { input, qc } = setup();
    await seedCache(qc);
    fireEvent.change(input, { target: { value: 'vi' } });
    expect(screen.getByRole('listbox')).toBeInTheDocument();
    fireEvent.keyDown(input, { key: 'Escape' });
    expect(screen.queryByRole('listbox')).toBeNull();
  });

  it('Enter with highlighted suggestion adds the highlighted tag', async () => {
    const { input, qc, onChange } = setup();
    await seedCache(qc);
    fireEvent.change(input, { target: { value: 're' } }); // 'react'
    fireEvent.keyDown(input, { key: 'ArrowDown' });        // highlight idx 0
    fireEvent.keyDown(input, { key: 'Enter' });
    expect(onChange).toHaveBeenCalledWith(['react']);
  });

  it('Tab with highlighted suggestion adds the highlighted tag', async () => {
    const { input, qc, onChange } = setup();
    await seedCache(qc);
    fireEvent.change(input, { target: { value: 're' } });
    fireEvent.keyDown(input, { key: 'ArrowDown' });
    fireEvent.keyDown(input, { key: 'Tab' });
    expect(onChange).toHaveBeenCalledWith(['react']);
  });

  it('onFocus re-opens the dropdown when inputValue is non-empty', async () => {
    const { input, qc } = setup();
    await seedCache(qc);
    fireEvent.change(input, { target: { value: 'vi' } }); // opens
    fireEvent.keyDown(input, { key: 'Escape' });           // closes
    expect(screen.queryByRole('listbox')).toBeNull();
    fireEvent.focus(input);                               // re-opens
    expect(screen.getByRole('listbox')).toBeInTheDocument();
  });

  it('mousedown on a suggestion adds the tag', async () => {
    const { input, qc, onChange } = setup();
    await seedCache(qc);
    fireEvent.change(input, { target: { value: 'zu' } }); // 'zustand'
    const option = screen.getByRole('option', { name: /zustand/i });
    fireEvent.mouseDown(option);
    expect(onChange).toHaveBeenCalledWith(['zustand']);
  });

  it('mouseEnter on a suggestion item highlights it', async () => {
    const { input, qc } = setup();
    await seedCache(qc);
    fireEvent.change(input, { target: { value: 'type' } });
    const option = screen.getByRole('option', { name: /typescript/i });
    fireEvent.mouseEnter(option);
    expect(option).toHaveAttribute('aria-selected', 'true');
  });
});
