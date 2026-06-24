/**
 * FrontmatterPanel.test.tsx
 *
 * Tests aligned to the ACTUAL FrontmatterPanel component:
 *  - Tags are stored as comma-separated text in a single <input> (no badge chips)
 *  - There is NO collapse toggle button — the panel is always expanded
 *  - onChange is called with a Partial<Frontmatter> object
 */
import React from 'react';
import { render, screen, fireEvent } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { FrontmatterPanel } from '../FrontmatterPanel';
import type { Frontmatter } from '../FrontmatterPanel';

const defaultFm: Frontmatter = {
  title: 'My Note',
  note_type: 'permanent',
  status: 'active',
  tags: ['dharma', 'buddhism'],
  folder: '10-zettelkasten',
  source_url: '',
  created_at: '2026-01-01',
  modified_at: '2026-01-02',
};

describe('FrontmatterPanel', () => {
  it('renders with initial title value', () => {
    render(<FrontmatterPanel fm={defaultFm} onChange={() => {}} />);
    expect(screen.getByDisplayValue('My Note')).toBeInTheDocument();
  });

  it('renders tags as comma-separated string in the tags input', () => {
    render(<FrontmatterPanel fm={defaultFm} onChange={() => {}} />);
    // Tags are joined with ", " into one input
    expect(screen.getByDisplayValue('dharma, buddhism')).toBeInTheDocument();
  });

  it('renders folder value', () => {
    render(<FrontmatterPanel fm={defaultFm} onChange={() => {}} />);
    expect(screen.getByDisplayValue('10-zettelkasten')).toBeInTheDocument();
  });

  it('calls onChange with updated title when title input changes', async () => {
    const onChange = vi.fn();
    const user = userEvent.setup();
    render(<FrontmatterPanel fm={defaultFm} onChange={onChange} />);
    const titleInput = screen.getByLabelText('Note title');
    await user.clear(titleInput);
    await user.type(titleInput, 'New Title');
    // Last call should have title starting with 'N'
    expect(onChange).toHaveBeenCalledWith(expect.objectContaining({ title: expect.stringContaining('N') }));
  });

  it('calls onChange with updated tags array when tags input changes', async () => {
    const onChange = vi.fn();
    const user = userEvent.setup();
    render(<FrontmatterPanel fm={defaultFm} onChange={onChange} />);
    const tagsInput = screen.getByLabelText('Note tags (comma separated)');
    await user.clear(tagsInput);
    await user.type(tagsInput, 'zen, meditation');
    // onChange should have been called with a tags array
    expect(onChange).toHaveBeenCalledWith(
      expect.objectContaining({ tags: expect.any(Array) }),
    );
  });

  it('calls onChange when note_type select changes', async () => {
    const onChange = vi.fn();
    const user = userEvent.setup();
    render(<FrontmatterPanel fm={defaultFm} onChange={onChange} />);
    const typeSelect = screen.getByLabelText('Note type');
    await user.selectOptions(typeSelect, 'literature');
    expect(onChange).toHaveBeenCalledWith(
      expect.objectContaining({ note_type: 'literature' }),
    );
  });

  it('calls onChange when status select changes', async () => {
    const onChange = vi.fn();
    const user = userEvent.setup();
    render(<FrontmatterPanel fm={defaultFm} onChange={onChange} />);
    const statusSelect = screen.getByLabelText('Note status');
    await user.selectOptions(statusSelect, 'done');
    expect(onChange).toHaveBeenCalledWith(
      expect.objectContaining({ status: 'done' }),
    );
  });

  it('renders created and modified timestamps', () => {
    render(<FrontmatterPanel fm={defaultFm} onChange={() => {}} />);
    expect(screen.getByText(/Created/)).toBeInTheDocument();
    expect(screen.getByText(/Modified/)).toBeInTheDocument();
  });

  it('disables all inputs when readonly=true', () => {
    render(<FrontmatterPanel fm={defaultFm} onChange={() => {}} readonly />);
    expect(screen.getByLabelText('Note title')).toBeDisabled();
    expect(screen.getByLabelText('Note tags (comma separated)')).toBeDisabled();
    expect(screen.getByLabelText('Note type')).toBeDisabled();
  });
});
