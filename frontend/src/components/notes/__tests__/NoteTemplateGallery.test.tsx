/**
 * NoteTemplateGallery.test.tsx
 * ============================
 * Mocks ../../services/api so that listTemplates() resolves immediately
 * with test fixtures instead of hanging forever in loading state.
 */
import React from 'react';
import { render, screen, fireEvent, waitFor, within } from '@testing-library/react';
import { vi, describe, it, beforeEach, expect } from 'vitest';

const MOCK_TEMPLATES = [
  {
    id: 'tpl-1',
    name: 'Project Plan',
    description: 'A structured project plan template.',
    note_type: 'permanent',
    folder: '20-projects',
    body: '## Overview\n\nDescribe the project.',
    icon: 'layout',
  },
  {
    id: 'tpl-2',
    name: 'Meeting Notes',
    description: 'Capture meeting notes and action items.',
    note_type: 'reference',
    folder: '30-resources',
    body: '## Attendees\n\n## Notes',
    icon: 'users',
  },
];

const mockListTemplates = vi.fn();

vi.mock('../../../services/api', () => ({
  default: {
    listTemplates: (...args: unknown[]) => mockListTemplates(...args),
  },
}));

beforeEach(() => {
  mockListTemplates.mockReset();
  mockListTemplates.mockResolvedValue(MOCK_TEMPLATES);
});

/** Wait for templates to load and return the list element. */
async function waitForList() {
  const list = await waitFor(() => screen.getByRole('list'), { timeout: 3000 });
  await waitFor(() => within(list).getByText('Project Plan'), { timeout: 3000 });
  return list;
}

import { NoteTemplateGallery } from '../NoteTemplateGallery';

describe('NoteTemplateGallery', () => {
  it('renders at least one template card', async () => {
    const onSelect = vi.fn();
    const onClose  = vi.fn();
    render(<NoteTemplateGallery onSelect={onSelect} onClose={onClose} />);
    const list = await waitForList();
    expect(within(list).getAllByRole('listitem').length).toBeGreaterThan(0);
  });

  it('calls onClose when the close button is clicked', async () => {
    const onClose = vi.fn();
    render(<NoteTemplateGallery onSelect={vi.fn()} onClose={onClose} />);
    fireEvent.click(screen.getByRole('button', { name: /close template gallery/i }));
    expect(onClose).toHaveBeenCalledOnce();
  });

  it('calls onSelect with the template object when Use Template is clicked', async () => {
    const onSelect = vi.fn();
    render(<NoteTemplateGallery onSelect={onSelect} onClose={vi.fn()} />);
    await waitForList();
    fireEvent.click(screen.getByRole('button', { name: /use this template/i }));
    expect(onSelect).toHaveBeenCalledWith(
      expect.objectContaining({ name: 'Project Plan' })
    );
  });

  it('renders template names as text', async () => {
    render(<NoteTemplateGallery onSelect={vi.fn()} onClose={vi.fn()} />);
    const list = await waitForList();
    expect(within(list).getByText('Project Plan')).toBeInTheDocument();
    expect(within(list).getByText('Meeting Notes')).toBeInTheDocument();
  });

  it('calls onClose when Cancel is clicked', () => {
    const onClose = vi.fn();
    render(<NoteTemplateGallery onSelect={vi.fn()} onClose={onClose} />);
    fireEvent.click(screen.getByRole('button', { name: /cancel/i }));
    expect(onClose).toHaveBeenCalledOnce();
  });
});
