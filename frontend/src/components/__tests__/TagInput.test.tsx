/**
 * TagInput
 * ========
 * Wraps with QueryClientProvider because TagInput calls useQuery for
 * tag autocomplete suggestions.
 *
 * What we test (11 cases):
 *  1.  Renders existing tags as chips
 *  2.  Renders the text input with placeholder
 *  3.  Enter key confirms a new tag and clears the input
 *  4.  Comma key confirms a new tag
 *  5.  Duplicate tags are not added
 *  6.  Whitespace-only input is ignored
 *  7.  Clicking the × button on a chip removes that tag
 *  8.  onChange is called with the updated tag list on add
 *  9.  onChange is called with the updated tag list on remove
 *  10. disabled prop disables the input
 *  11. Tab key confirms a new tag
 */

import { describe, it, expect, vi, afterEach } from 'vitest';
import { render, screen, fireEvent } from '@testing-library/react';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import React from 'react';
import TagInput from '../TagInput';

// Mock api.listTags used by TagInput's autocomplete query
vi.mock('../../services/api', () => ({
  default: { listTags: vi.fn().mockResolvedValue([]) },
}));

function makeQC() {
  return new QueryClient({ defaultOptions: { queries: { retry: false } } });
}

function renderTagInput(
  tags: string[] = [],
  onChange = vi.fn(),
  props: Record<string, unknown> = {},
) {
  return render(
    <QueryClientProvider client={makeQC()}>
      <TagInput
        tags={tags}
        onChange={onChange}
        placeholder="Add tags…"
        {...props}
      />
    </QueryClientProvider>,
  );
}

afterEach(() => vi.clearAllMocks());

describe('TagInput rendering', () => {
  it('renders existing tags as chips', () => {
    renderTagInput(['alpha', 'beta']);
    expect(screen.getByText('alpha')).toBeInTheDocument();
    expect(screen.getByText('beta')).toBeInTheDocument();
  });

  it('renders input with placeholder', () => {
    renderTagInput();
    expect(screen.getByPlaceholderText('Add tags…')).toBeInTheDocument();
  });

  it('input is disabled when disabled prop is true', () => {
    renderTagInput([], undefined, { disabled: true });
    expect(screen.getByPlaceholderText('Add tags…')).toBeDisabled();
  });
});

describe('adding tags', () => {
  it('Enter confirms a new tag and clears the input', () => {
    const onChange = vi.fn();
    renderTagInput(['existing'], onChange);
    const input = screen.getByPlaceholderText('Add tags…');
    fireEvent.change(input, { target: { value: 'newtag' } });
    fireEvent.keyDown(input, { key: 'Enter' });
    expect(onChange).toHaveBeenCalledWith(['existing', 'newtag']);
    expect(input).toHaveValue('');
  });

  it('Comma confirms a new tag', () => {
    const onChange = vi.fn();
    renderTagInput([], onChange);
    const input = screen.getByPlaceholderText('Add tags…');
    fireEvent.change(input, { target: { value: 'csv' } });
    fireEvent.keyDown(input, { key: ',' });
    expect(onChange).toHaveBeenCalledWith(['csv']);
  });

  it('Tab confirms a new tag', () => {
    const onChange = vi.fn();
    renderTagInput([], onChange);
    const input = screen.getByPlaceholderText('Add tags…');
    fireEvent.change(input, { target: { value: 'tabbed' } });
    fireEvent.keyDown(input, { key: 'Tab' });
    expect(onChange).toHaveBeenCalledWith(['tabbed']);
  });

  it('duplicate tags are not added', () => {
    const onChange = vi.fn();
    renderTagInput(['alpha'], onChange);
    const input = screen.getByPlaceholderText('Add tags…');
    fireEvent.change(input, { target: { value: 'alpha' } });
    fireEvent.keyDown(input, { key: 'Enter' });
    expect(onChange).not.toHaveBeenCalled();
  });

  it('whitespace-only input is ignored', () => {
    const onChange = vi.fn();
    renderTagInput([], onChange);
    const input = screen.getByPlaceholderText('Add tags…');
    fireEvent.change(input, { target: { value: '   ' } });
    fireEvent.keyDown(input, { key: 'Enter' });
    expect(onChange).not.toHaveBeenCalled();
  });
});

describe('removing tags', () => {
  it('clicking × removes that tag', () => {
    const onChange = vi.fn();
    renderTagInput(['alpha', 'beta'], onChange);
    const removeButtons = screen.getAllByRole('button');
    fireEvent.click(removeButtons[0]);
    expect(onChange).toHaveBeenCalledWith(['beta']);
  });

  it('onChange called with updated list on remove', () => {
    const onChange = vi.fn();
    renderTagInput(['x', 'y', 'z'], onChange);
    const removeButtons = screen.getAllByRole('button');
    fireEvent.click(removeButtons[1]); // remove 'y'
    expect(onChange).toHaveBeenCalledWith(['x', 'z']);
  });
});
