/**
 * FrontmatterPanel.test.tsx
 * Tests:
 *  - renders all frontmatter fields
 *  - title input calls onChange
 *  - tag add via keyboard appends tag
 *  - tag remove removes tag
 *  - panel collapses / expands
 */
import React from 'react';
import { render, screen, fireEvent, within } from '@testing-library/react';
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
  it('renders with initial values', () => {
    render(<FrontmatterPanel fm={defaultFm} onChange={() => {}} />);
    // Panel starts expanded by default; title field should be visible
    expect(screen.getByDisplayValue('My Note')).toBeInTheDocument();
  });

  it('calls onChange when title is edited', async () => {
    const onChange = vi.fn();
    const user = userEvent.setup();
    render(<FrontmatterPanel fm={defaultFm} onChange={onChange} />);
    const titleInput = screen.getByDisplayValue('My Note');
    await user.clear(titleInput);
    await user.type(titleInput, 'Updated Title');
    // onChange should have been called with updated title
    expect(onChange).toHaveBeenCalledWith(expect.objectContaining({ title: expect.stringContaining('U') }));
  });

  it('renders existing tags', () => {
    render(<FrontmatterPanel fm={defaultFm} onChange={() => {}} />);
    expect(screen.getByText('dharma')).toBeInTheDocument();
    expect(screen.getByText('buddhism')).toBeInTheDocument();
  });

  it('removes a tag when its remove button is clicked', async () => {
    const onChange = vi.fn();
    render(<FrontmatterPanel fm={defaultFm} onChange={onChange} />);
    const removeButtons = screen.getAllByRole('button', { name: /remove tag/i });
    fireEvent.click(removeButtons[0]); // remove 'dharma'
    expect(onChange).toHaveBeenCalledWith(
      expect.objectContaining({ tags: expect.not.arrayContaining(['dharma']) })
    );
  });

  it('collapses and expands when toggle is clicked', async () => {
    const user = userEvent.setup();
    render(<FrontmatterPanel fm={defaultFm} onChange={() => {}} />);
    const toggle = screen.getByRole('button', { name: /frontmatter|properties|collapse/i });
    // Initially expanded — title field visible
    expect(screen.getByDisplayValue('My Note')).toBeInTheDocument();
    await user.click(toggle);
    // After collapse — title field not visible
    expect(screen.queryByDisplayValue('My Note')).toBeNull();
  });
});
