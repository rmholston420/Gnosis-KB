/**
 * NoteTemplateGallery.test.tsx
 * ============================
 * Tests for the template picker modal that inserts starter content.
 *
 * The component loads templates via api.listTemplates() which we mock
 * so tests are fully synchronous / deterministic.
 */
import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import NoteTemplateGallery from '../NoteTemplateGallery';

// ---------- mock api ----------
const mockListTemplates = vi.fn();
vi.mock('../../../services/api', () => ({
  default: { listTemplates: (...args: unknown[]) => mockListTemplates(...args) },
}));

const SAMPLE_TEMPLATES = [
  { id: 't1', name: 'Project Plan',  description: 'Plan a project',  note_type: 'reference', folder: 'projects', body: '# Project\n', icon: 'layout' },
  { id: 't2', name: 'Daily Journal', description: 'Daily log',       note_type: 'fleeting',  folder: 'journals',  body: '## Today\n',  icon: 'sun' },
  { id: 't3', name: 'Blank Note',    description: 'Empty canvas',    note_type: 'fleeting',  folder: '00-inbox',  body: '',          icon: 'file' },
];

beforeEach(() => {
  mockListTemplates.mockReset();
  mockListTemplates.mockResolvedValue(SAMPLE_TEMPLATES);
});

function renderGallery(onSelect = vi.fn(), onClose = vi.fn()) {
  return render(<NoteTemplateGallery onSelect={onSelect} onClose={onClose} />);
}

describe('NoteTemplateGallery', () => {
  it('renders the gallery heading', async () => {
    renderGallery();
    // Use getByRole to be specific — the <h2> heading element
    expect(screen.getByRole('heading', { name: /choose a template/i })).toBeInTheDocument();
  });

  it('renders at least one template card', async () => {
    renderGallery();
    // Wait for async load
    await waitFor(() => screen.getByText('Project Plan'));
    const cards = screen.getAllByRole('button');
    expect(cards.length).toBeGreaterThan(0);
  });

  it('renders a Close button in the header', () => {
    renderGallery();
    // The ×  header button has aria-label="Close template gallery"
    expect(screen.getByRole('button', { name: /close template gallery/i })).toBeInTheDocument();
  });

  it('renders a Cancel button in the footer', () => {
    renderGallery();
    expect(screen.getByRole('button', { name: /^cancel$/i })).toBeInTheDocument();
  });

  it('calls onClose when Close button is clicked', () => {
    const onClose = vi.fn();
    renderGallery(vi.fn(), onClose);
    fireEvent.click(screen.getByRole('button', { name: /close template gallery/i }));
    expect(onClose).toHaveBeenCalledTimes(1);
  });

  it('calls onClose when Cancel button is clicked', () => {
    const onClose = vi.fn();
    renderGallery(vi.fn(), onClose);
    fireEvent.click(screen.getByRole('button', { name: /^cancel$/i }));
    expect(onClose).toHaveBeenCalledTimes(1);
  });

  it('calls onSelect with the template object when Use Template is clicked', async () => {
    const onSelect = vi.fn();
    renderGallery(onSelect);
    await waitFor(() => screen.getByText('Project Plan'));
    // Click the first template card to select it
    fireEvent.click(screen.getByText('Project Plan'));
    // Click Use Template
    fireEvent.click(screen.getByRole('button', { name: /use template/i }));
    expect(onSelect).toHaveBeenCalledWith(expect.objectContaining({ id: 't1' }));
  });

  it('renders template names as text', async () => {
    renderGallery();
    await waitFor(() => screen.getByText('Project Plan'));
    expect(screen.getByText('Project Plan')).toBeInTheDocument();
    expect(screen.getByText('Daily Journal')).toBeInTheDocument();
    expect(screen.getByText('Blank Note')).toBeInTheDocument();
  });
});
