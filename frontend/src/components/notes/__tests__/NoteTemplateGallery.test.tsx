/**
 * NoteTemplateGallery.test.tsx
 * ============================
 * Tests for the template picker modal that inserts starter content.
 */
import { describe, it, expect, vi } from 'vitest';
import { render, screen, fireEvent } from '@testing-library/react';
import NoteTemplateGallery from '../NoteTemplateGallery';

function renderGallery(onSelect = vi.fn(), onClose = vi.fn()) {
  return render(<NoteTemplateGallery onSelect={onSelect} onClose={onClose} />);
}

describe('NoteTemplateGallery', () => {
  it('renders the gallery heading', () => {
    renderGallery();
    expect(screen.getByText(/template/i)).toBeInTheDocument();
  });

  it('renders at least one template card', () => {
    renderGallery();
    // Each card has a clickable role — buttons or listitem
    const cards = screen.getAllByRole('button');
    expect(cards.length).toBeGreaterThan(0);
  });

  it('renders a Close / Cancel button', () => {
    renderGallery();
    expect(screen.getByRole('button', { name: /close|cancel/i })).toBeInTheDocument();
  });

  it('calls onClose when Close button is clicked', () => {
    const onClose = vi.fn();
    renderGallery(vi.fn(), onClose);
    fireEvent.click(screen.getByRole('button', { name: /close|cancel/i }));
    expect(onClose).toHaveBeenCalledTimes(1);
  });

  it('calls onSelect with template content when a card is clicked', () => {
    const onSelect = vi.fn();
    renderGallery(onSelect);
    // Click first non-close button (a template card)
    const buttons = screen.getAllByRole('button');
    const templateCard = buttons.find(
      (b) => !b.textContent?.match(/close|cancel/i)
    )!;
    fireEvent.click(templateCard);
    expect(onSelect).toHaveBeenCalledWith(expect.any(String));
  });

  it('renders template names as text', () => {
    renderGallery();
    // At least one recognisable template name should appear
    const hasKnownTemplate = [
      /fleeting/i, /permanent/i, /literature/i, /journal/i, /meeting/i,
      /project/i, /daily/i, /blank/i, /map/i, /reference/i,
    ].some((re) => screen.queryByText(re));
    expect(hasKnownTemplate).toBe(true);
  });
});
