/**
 * TagInput
 * ========
 * Tests for the inline tag editor used in NoteEditor.
 *
 * Cases (10):
 *  1.  Renders existing tags
 *  2.  Enter key adds a tag and clears input
 *  3.  Comma key adds a tag
 *  4.  Duplicate tags are not added
 *  5.  Whitespace-only input is rejected
 *  6.  Backspace on empty input removes the last tag
 *  7.  Clicking × on a tag removes it
 *  8.  onChange is called with the new array after add
 *  9.  onChange is called with the new array after remove
 *  10. Input is disabled when disabled=true
 */

import { describe, it, expect, vi, afterEach } from 'vitest';
import { render, screen, fireEvent } from '@testing-library/react';
import React from 'react';
import TagInput from '../TagInput';

function setup(
  tags: string[] = [],
  onChange = vi.fn(),
  disabled = false,
) {
  return render(<TagInput tags={tags} onChange={onChange} disabled={disabled} />);
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

  it('ignores whitespace-only input', () => {
    const onChange = vi.fn();
    setup([], onChange);
    const input = screen.getByRole('textbox');
    fireEvent.change(input, { target: { value: '   ' } });
    fireEvent.keyDown(input, { key: 'Enter' });
    expect(onChange).not.toHaveBeenCalled();
  });

  it('Backspace on empty input removes last tag', () => {
    const onChange = vi.fn();
    setup(['alpha', 'beta'], onChange);
    const input = screen.getByRole('textbox');
    fireEvent.keyDown(input, { key: 'Backspace' });
    expect(onChange).toHaveBeenCalledWith(['alpha']);
  });

  it('clicking × removes the tag', () => {
    const onChange = vi.fn();
    setup(['alpha', 'beta'], onChange);
    // Each tag has a remove button (×)
    const removeButtons = screen.getAllByRole('button');
    fireEvent.click(removeButtons[0]); // removes 'alpha'
    expect(onChange).toHaveBeenCalledWith(['beta']);
  });

  it('onChange called with new array after add', () => {
    const onChange = vi.fn();
    setup(['existing'], onChange);
    const input = screen.getByRole('textbox');
    fireEvent.change(input, { target: { value: 'new' } });
    fireEvent.keyDown(input, { key: 'Enter' });
    expect(onChange).toHaveBeenCalledWith(['existing', 'new']);
  });

  it('onChange called with new array after remove', () => {
    const onChange = vi.fn();
    setup(['alpha', 'beta'], onChange);
    const removeButtons = screen.getAllByRole('button');
    fireEvent.click(removeButtons[1]); // removes 'beta'
    expect(onChange).toHaveBeenCalledWith(['alpha']);
  });

  it('input is disabled when disabled=true', () => {
    setup([], vi.fn(), true);
    expect(screen.getByRole('textbox')).toBeDisabled();
  });
});
