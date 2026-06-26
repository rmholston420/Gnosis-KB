/**
 * NoteTemplateGallery.test.tsx
 * ============================
 * NoteTemplateGallery was refactored to use BUILT_IN_TEMPLATES (client-side
 * constant) instead of calling api.listTemplates().  The api mock is kept
 * for safety but the tests now assert against titles that exist in
 * BUILT_IN_TEMPLATES rather than mock API fixtures.
 *
 * BUILT_IN_TEMPLATES includes: Blank Note, Permanent Note, Literature Note,
 * Fleeting Note, Map of Content, Daily Note, Meeting Note.
 */
import React from 'react';
import { render, screen, fireEvent, waitFor, within } from '@testing-library/react';
import { vi, describe, it, beforeEach, expect } from 'vitest';

// Keep the mock in place in case a future code path re-introduces the API call.
const mockListTemplates = vi.fn();
vi.mock('../../../services/api', () => ({
  default: {
    listTemplates: (...args: unknown[]) => mockListTemplates(...args),
  },
}));

beforeEach(() => {
  mockListTemplates.mockReset();
  mockListTemplates.mockResolvedValue([]);
});

/** Wait for the template list to appear and contain a known built-in title. */
async function waitForList() {
  const list = await waitFor(() => screen.getByRole('list'), { timeout: 3000 });
  // "Permanent Note" is the second BUILT_IN_TEMPLATE and always present.
  await waitFor(() => within(list).getByText('Permanent Note'), { timeout: 3000 });
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
    // The first template (Blank Note) is selected by default;
    // clicking "Use this template" should call onSelect with it.
    fireEvent.click(screen.getByRole('button', { name: /use this template/i }));
    expect(onSelect).toHaveBeenCalledWith(
      expect.objectContaining({ name: 'Blank Note' })
    );
  });

  it('renders template names as text', async () => {
    render(<NoteTemplateGallery onSelect={vi.fn()} onClose={vi.fn()} />);
    const list = await waitForList();
    // Assert a representative subset of BUILT_IN_TEMPLATES
    expect(within(list).getByText('Blank Note')).toBeInTheDocument();
    expect(within(list).getByText('Permanent Note')).toBeInTheDocument();
    expect(within(list).getByText('Meeting Note')).toBeInTheDocument();
  });

  it('calls onClose when Cancel is clicked', () => {
    const onClose = vi.fn();
    render(<NoteTemplateGallery onSelect={vi.fn()} onClose={onClose} />);
    fireEvent.click(screen.getByRole('button', { name: /cancel/i }));
    expect(onClose).toHaveBeenCalledOnce();
  });
});
