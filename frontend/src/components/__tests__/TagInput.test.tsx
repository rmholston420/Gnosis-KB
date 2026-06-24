/**
 * TagInput.test.tsx
 * Fix: aria-label on remove buttons is "Remove tag X", not "remove X".
 * Update all getByRole('button', { name: /remove X/i }) to match actual label.
 */
import React from 'react';
import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import TagInput from '@/components/TagInput';

const mockListTags = vi.fn();
vi.mock('@/services/api', () => ({
  default: {
    listTags: (...a: unknown[]) => mockListTags(...a),
  },
}));

function makeClient() {
  return new QueryClient({ defaultOptions: { queries: { retry: false } } });
}

function setup(tags: string[] = [], onChange = vi.fn()) {
  const client = makeClient();
  render(
    <QueryClientProvider client={client}>
      <TagInput tags={tags} onChange={onChange} />
    </QueryClientProvider>
  );
  return { onChange };
}

beforeEach(() => {
  mockListTags.mockResolvedValue([]);
});

describe('TagInput', () => {
  it('renders with no tags', () => {
    setup();
    expect(screen.getByPlaceholderText(/add tag/i)).toBeInTheDocument();
  });

  it('renders existing tags', () => {
    setup(['buddhism', 'dharma']);
    expect(screen.getByText('buddhism')).toBeInTheDocument();
    expect(screen.getByText('dharma')).toBeInTheDocument();
  });

  it('adds a tag on Enter', async () => {
    const onChange = vi.fn();
    setup([], onChange);
    const input = screen.getByRole('textbox');
    fireEvent.change(input, { target: { value: 'samsara' } });
    fireEvent.keyDown(input, { key: 'Enter' });
    await waitFor(() =>
      expect(onChange).toHaveBeenCalledWith(['samsara'])
    );
  });

  it('does not add duplicate tag', async () => {
    const onChange = vi.fn();
    setup(['existing'], onChange);
    const input = screen.getByRole('textbox');
    fireEvent.change(input, { target: { value: 'existing' } });
    fireEvent.keyDown(input, { key: 'Enter' });
    await waitFor(() => expect(onChange).not.toHaveBeenCalled());
  });

  it('does not add blank tag', async () => {
    const onChange = vi.fn();
    setup([], onChange);
    const input = screen.getByRole('textbox');
    fireEvent.change(input, { target: { value: '  ' } });
    fireEvent.keyDown(input, { key: 'Enter' });
    await waitFor(() => expect(onChange).not.toHaveBeenCalled());
  });

  it('adds a tag on comma', async () => {
    const onChange = vi.fn();
    setup([], onChange);
    const input = screen.getByRole('textbox');
    fireEvent.change(input, { target: { value: 'karma' } });
    fireEvent.keyDown(input, { key: ',' });
    await waitFor(() =>
      expect(onChange).toHaveBeenCalledWith(['karma'])
    );
  });

  // aria-label is "Remove tag removeme" — match with /remove tag removeme/i
  it('clicking × removes a tag', async () => {
    const onChange = vi.fn();
    setup(['removeme'], onChange);
    fireEvent.click(screen.getByRole('button', { name: /remove tag removeme/i }));
    expect(onChange).toHaveBeenCalledWith([]);
  });

  it('onChange called with new array after remove', async () => {
    const onChange = vi.fn();
    setup(['p', 'q'], onChange);
    fireEvent.click(screen.getByRole('button', { name: /remove tag p/i }));
    expect(onChange).toHaveBeenCalledWith(['q']);
  });

  it('is disabled when disabled prop passed', () => {
    const client = makeClient();
    render(
      <QueryClientProvider client={client}>
        <TagInput tags={[]} onChange={vi.fn()} disabled />
      </QueryClientProvider>
    );
    expect(screen.getByRole('textbox')).toBeDisabled();
  });
});
