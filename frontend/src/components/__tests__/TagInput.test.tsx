/**
 * TagInput
 * ========
 * Tests for the inline tag editor used in NoteEditor.
 */

import { describe, it, expect, vi, afterEach } from 'vitest';
import { render, screen, fireEvent } from '@testing-library/react';
import React from 'react';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import TagInput from '../TagInput';

vi.mock('../../services/api', () => ({
  default: {
    listTags: vi.fn().mockResolvedValue([]),
  },
}));

function makeClient() {
  return new QueryClient({
    defaultOptions: {
      queries: { retry: false, gcTime: 0 },
    },
  });
}

function setup(
  tags: string[] = [],
  onChange = vi.fn(),
  disabled = false,
) {
  const client = makeClient();
  return render(
    <QueryClientProvider client={client}>
      <TagInput tags={tags} onChange={onChange} disabled={disabled} />
    </QueryClientProvider>,
  );
}

afterEach(() => { vi.clearAllMocks(); });

describe('TagInput', () => {
  it('renders existing tags', () => {
    setup(['alpha', 'beta']);
    expect(screen.getByText('alpha')).toBeInTheDocument();
    expect(screen.getByText('beta')).toBeInTheDocument();
  });

  it('Enter key adds a tag and clears the input', () => {
    const onChange = vi.fn();
    setup([], onChange);
    const input = screen.getByRole('textbox');
    fireEvent.change(input, { target: { value: 'new-tag' } });
    fireEvent.keyDown(input, { key: 'Enter' });
    expect(onChange).toHaveBeenCalledWith(['new-tag']);
    expect(input).toHaveValue('');
  });

  it('Comma key adds a tag', () => {
    const onChange = vi.fn();
    setup([], onChange);
    const input = screen.getByRole('textbox');
    fireEvent.change(input, { target: { value: 'tag-comma' } });
    fireEvent.keyDown(input, { key: ',' });
    expect(onChange).toHaveBeenCalledWith(['tag-comma']);
  });

  it('does not add duplicate tags', () => {
    const onChange = vi.fn();
    setup(['existing'], onChange);
    const input = screen.getByRole('textbox');
    fireEvent.change(input, { target: { value: 'existing' } });
    fireEvent.keyDown(input, { key: 'Enter' });
    expect(onChange).not.toHaveBeenCalled();
  });

  it('rejects whitespace-only input', () => {
    const onChange = vi.fn();
    setup([], onChange);
    const input = screen.getByRole('textbox');
    fireEvent.change(input, { target: { value: '   ' } });
    fireEvent.keyDown(input, { key: 'Enter' });
    expect(onChange).not.toHaveBeenCalled();
  });

  it('Backspace on empty input removes last tag', () => {
    const onChange = vi.fn();
    setup(['a', 'b'], onChange);
    const input = screen.getByRole('textbox');
    fireEvent.keyDown(input, { key: 'Backspace' });
    expect(onChange).toHaveBeenCalledWith(['a']);
  });

  it('clicking × removes a tag', () => {
    const onChange = vi.fn();
    setup(['removeme'], onChange);
    fireEvent.click(screen.getByRole('button', { name: /remove removeme/i }));
    expect(onChange).toHaveBeenCalledWith([]);
  });

  it('onChange called with new array after add', () => {
    const onChange = vi.fn();
    setup(['x'], onChange);
    const input = screen.getByRole('textbox');
    fireEvent.change(input, { target: { value: 'y' } });
    fireEvent.keyDown(input, { key: 'Enter' });
    expect(onChange).toHaveBeenCalledWith(['x', 'y']);
  });

  it('onChange called with new array after remove', () => {
    const onChange = vi.fn();
    setup(['p', 'q'], onChange);
    fireEvent.click(screen.getByRole('button', { name: /remove p/i }));
    expect(onChange).toHaveBeenCalledWith(['q']);
  });

  it('input is disabled when disabled=true', () => {
    setup([], vi.fn(), true);
    expect(screen.getByRole('textbox')).toBeDisabled();
  });
});
