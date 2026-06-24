/**
 * LightRagNodePanel.test.tsx
 * ==========================
 * Tests for the graph entity detail side-panel.
 *
 * The component accepts synchronous props:
 *   entity: LightRagEntity | null
 *   relations: LightRagRelation[]
 *   notes: NoteListItem[]
 *   onClose: () => void
 *   onNavigateToNote: (noteId: string) => void
 *
 * No async API calls — everything is driven via props.
 */
import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, fireEvent } from '@testing-library/react';
import LightRagNodePanel, {
  type LightRagEntity,
  type LightRagRelation,
  type NoteListItem,
} from '../LightRagNodePanel';

const sampleEntity: LightRagEntity = {
  id: 'node-1',
  label: 'Dependent Origination',
  description: 'The teaching of interdependent causation.',
  source_note_ids: ['note-a'],
};

const sampleRelations: LightRagRelation[] = [
  { source: 'node-1', target: 'node-2', label: 'related to', weight: 0.9 },
  { source: 'node-3', target: 'node-1', label: 'causes',     weight: 0.7 },
];

const sampleNotes: NoteListItem[] = [
  { id: 'note-a', title: 'Introduction to Pratītyasamutpāda', folder: 'buddhism' },
];

function renderPanel(
  entity: LightRagEntity | null = sampleEntity,
  relations: LightRagRelation[] = sampleRelations,
  notes: NoteListItem[] = sampleNotes,
  onClose = vi.fn(),
  onNavigateToNote = vi.fn(),
) {
  return render(
    <LightRagNodePanel
      entity={entity}
      relations={relations}
      notes={notes}
      onClose={onClose}
      onNavigateToNote={onNavigateToNote}
    />
  );
}

beforeEach(() => {
  // nothing async to reset
});

describe('LightRagNodePanel', () => {
  it('renders nothing when entity is null', () => {
    const { container } = renderPanel(null);
    expect(container.firstChild).toBeNull();
  });

  it('renders the entity title', () => {
    renderPanel();
    expect(screen.getByText('Dependent Origination')).toBeInTheDocument();
  });

  it('renders the entity description', () => {
    renderPanel();
    expect(screen.getByText(/interdependent causation/i)).toBeInTheDocument();
  });

  it('renders incident relations', () => {
    renderPanel();
    expect(screen.getByText('related to')).toBeInTheDocument();
    expect(screen.getByText('causes')).toBeInTheDocument();
  });

  it('renders source note links', () => {
    renderPanel();
    expect(
      screen.getByText(/Pratītyasamutpāda/i)
    ).toBeInTheDocument();
  });

  it('calls onNavigateToNote when a source note is clicked', () => {
    const onNavigateToNote = vi.fn();
    renderPanel(sampleEntity, sampleRelations, sampleNotes, vi.fn(), onNavigateToNote);
    fireEvent.click(screen.getByText(/Pratītyasamutpāda/i));
    expect(onNavigateToNote).toHaveBeenCalledWith('note-a');
  });

  it('calls onClose when Close button is clicked', () => {
    const onClose = vi.fn();
    renderPanel(sampleEntity, sampleRelations, sampleNotes, onClose);
    fireEvent.click(screen.getByRole('button', { name: /close entity panel/i }));
    expect(onClose).toHaveBeenCalledTimes(1);
  });

  it('calls onClose when Escape is pressed', () => {
    const onClose = vi.fn();
    renderPanel(sampleEntity, sampleRelations, sampleNotes, onClose);
    fireEvent.keyDown(window, { key: 'Escape' });
    expect(onClose).toHaveBeenCalledTimes(1);
  });

  it('panel has correct ARIA role and label', () => {
    renderPanel();
    const panel = screen.getByRole('complementary');
    expect(panel).toHaveAttribute('aria-label', expect.stringMatching(/entity panel/i));
  });

  it('shows empty state when entity has no description or relations', () => {
    const sparse: LightRagEntity = { id: 'x', label: 'Unknown' };
    renderPanel(sparse, [], []);
    expect(screen.getByText(/no additional information/i)).toBeInTheDocument();
  });
});
