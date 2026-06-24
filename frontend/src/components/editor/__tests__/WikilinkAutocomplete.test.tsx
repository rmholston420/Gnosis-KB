import React from 'react';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import { describe, it, expect, vi, beforeEach } from 'vitest';
import WikilinkAutocomplete, { useWikilinkDetector } from '@/components/editor/WikilinkAutocomplete';

const mockListNotes = vi.fn();
vi.mock('@/services/api', () => ({
  default: { listNotes: (...a: unknown[]) => mockListNotes(...a) },
}));

const NOTES = [
  { id: '1', title: 'Alpha Note' },
  { id: '2', title: 'Beta Note' },
  { id: '3', title: 'Gamma Note' },
];
const BASE_RECT = new DOMRect(100, 200, 0, 0);

describe('WikilinkAutocomplete', () => {
  beforeEach(() => vi.clearAllMocks());

  it('renders nothing when items list is empty', async () => {
    mockListNotes.mockResolvedValue({ items: [] });
    render(<WikilinkAutocomplete query="xyz" anchorRect={BASE_RECT} onSelect={vi.fn()} onClose={vi.fn()} />);
    await new Promise((r) => setTimeout(r, 50));
    expect(screen.queryByRole('listbox')).toBeNull();
  });

  it('renders listbox with { items } response shape', async () => {
    mockListNotes.mockResolvedValue({ items: NOTES });
    render(<WikilinkAutocomplete query="" anchorRect={BASE_RECT} onSelect={vi.fn()} onClose={vi.fn()} />);
    await waitFor(() => expect(screen.getByRole('listbox')).toBeTruthy());
  });

  it('renders listbox with bare array response shape', async () => {
    mockListNotes.mockResolvedValue(NOTES);
    render(<WikilinkAutocomplete query="" anchorRect={BASE_RECT} onSelect={vi.fn()} onClose={vi.fn()} />);
    await waitFor(() => expect(screen.getByRole('listbox')).toBeTruthy());
  });

  it('renders listbox with { data } response shape', async () => {
    mockListNotes.mockResolvedValue({ data: NOTES });
    render(<WikilinkAutocomplete query="" anchorRect={BASE_RECT} onSelect={vi.fn()} onClose={vi.fn()} />);
    await waitFor(() => expect(screen.getByRole('listbox')).toBeTruthy());
  });

  it('calls onSelect when item clicked', async () => {
    mockListNotes.mockResolvedValue({ items: NOTES });
    const onSelect = vi.fn();
    render(<WikilinkAutocomplete query="al" anchorRect={BASE_RECT} onSelect={onSelect} onClose={vi.fn()} />);
    await waitFor(() => screen.getByRole('listbox'));
    fireEvent.click(screen.getAllByRole('option')[0]);
    expect(onSelect).toHaveBeenCalledWith(NOTES[0].title);
  });

  it('calls onClose on Escape key via window listener', async () => {
    mockListNotes.mockResolvedValue({ items: NOTES });
    const onClose = vi.fn();
    render(<WikilinkAutocomplete query="" anchorRect={BASE_RECT} onSelect={vi.fn()} onClose={onClose} />);
    await waitFor(() => screen.getByRole('listbox'));
    fireEvent.keyDown(window, { key: 'Escape' });
    expect(onClose).toHaveBeenCalled();
  });

  it('ArrowDown then Enter selects first item', async () => {
    mockListNotes.mockResolvedValue({ items: NOTES });
    const onSelect = vi.fn();
    render(<WikilinkAutocomplete query="" anchorRect={BASE_RECT} onSelect={onSelect} onClose={vi.fn()} />);
    await waitFor(() => screen.getByRole('listbox'));
    fireEvent.keyDown(window, { key: 'ArrowDown' });
    fireEvent.keyDown(window, { key: 'Enter' });
    expect(onSelect).toHaveBeenCalled();
  });

  it('Tab key selects active item', async () => {
    mockListNotes.mockResolvedValue({ items: NOTES });
    const onSelect = vi.fn();
    render(<WikilinkAutocomplete query="" anchorRect={BASE_RECT} onSelect={onSelect} onClose={vi.fn()} />);
    await waitFor(() => screen.getByRole('listbox'));
    fireEvent.keyDown(window, { key: 'Tab' });
    expect(onSelect).toHaveBeenCalled();
  });

  it('ArrowUp navigation does not crash', async () => {
    mockListNotes.mockResolvedValue({ items: NOTES });
    render(<WikilinkAutocomplete query="" anchorRect={BASE_RECT} onSelect={vi.fn()} onClose={vi.fn()} />);
    await waitFor(() => screen.getByRole('listbox'));
    fireEvent.keyDown(window, { key: 'ArrowDown' });
    fireEvent.keyDown(window, { key: 'ArrowDown' });
    fireEvent.keyDown(window, { key: 'ArrowUp' });
  });

  it('ul onKeyDown ArrowDown works', async () => {
    mockListNotes.mockResolvedValue({ items: NOTES });
    render(<WikilinkAutocomplete query="" anchorRect={BASE_RECT} onSelect={vi.fn()} onClose={vi.fn()} />);
    await waitFor(() => screen.getByRole('listbox'));
    fireEvent.keyDown(screen.getByRole('listbox'), { key: 'ArrowDown' });
  });

  it('ul onKeyDown Escape works', async () => {
    mockListNotes.mockResolvedValue({ items: NOTES });
    const onClose = vi.fn();
    render(<WikilinkAutocomplete query="" anchorRect={BASE_RECT} onSelect={vi.fn()} onClose={onClose} />);
    await waitFor(() => screen.getByRole('listbox'));
    fireEvent.keyDown(screen.getByRole('listbox'), { key: 'Escape' });
    expect(onClose).toHaveBeenCalled();
  });

  it('handles api rejection gracefully — renders nothing', async () => {
    mockListNotes.mockRejectedValue(new Error('fail'));
    render(<WikilinkAutocomplete query="err" anchorRect={BASE_RECT} onSelect={vi.fn()} onClose={vi.fn()} />);
    await new Promise((r) => setTimeout(r, 60));
    expect(screen.queryByRole('listbox')).toBeNull();
  });
});

function Harness({
  value,
  onChange,
}: {
  value: string;
  onChange: (v: string) => void;
}) {
  const ref = React.useRef<HTMLTextAreaElement>(null);
  const { wikilinkQuery, insertWikilink } = useWikilinkDetector(ref, value, onChange);
  return (
    <div>
      <textarea ref={ref} defaultValue={value} data-testid="ta" />
      <span data-testid="q">{wikilinkQuery ?? 'null'}</span>
      <button data-testid="ins" onClick={() => insertWikilink('InsertedTitle')}>
        Insert
      </button>
    </div>
  );
}

describe('useWikilinkDetector', () => {
  it('returns null wikilinkQuery initially', () => {
    render(<Harness value="" onChange={vi.fn()} />);
    expect(screen.getByTestId('q').textContent).toBe('null');
  });

  it('fires keyup event on textarea without crashing', () => {
    render(<Harness value="[[abc" onChange={vi.fn()} />);
    fireEvent.keyUp(screen.getByTestId('ta'));
  });

  it('fires click event on textarea without crashing', () => {
    render(<Harness value="[[abc" onChange={vi.fn()} />);
    fireEvent.click(screen.getByTestId('ta'));
  });

  it('insertWikilink with no [[ in value does not throw', () => {
    render(<Harness value="no brackets here" onChange={vi.fn()} />);
    fireEvent.click(screen.getByTestId('ins'));
  });

  it('insertWikilink with [[ in value calls onChange', () => {
    const onChange = vi.fn();
    render(<Harness value="type [[partial" onChange={onChange} />);
    fireEvent.click(screen.getByTestId('ins'));
    expect(onChange).toHaveBeenCalledWith('type [[InsertedTitle]]');
  });
});
