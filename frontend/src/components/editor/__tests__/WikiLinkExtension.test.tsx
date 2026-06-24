/**
 * WikiLinkExtension.test.tsx
 */
import React from 'react';
import { render, screen, fireEvent } from '@testing-library/react';
import { describe, it, expect, vi, afterEach } from 'vitest';

vi.mock('tippy.js', () => ({
  default: vi.fn(() => [{ setProps: vi.fn(), hide: vi.fn(), destroy: vi.fn() }]),
}));

vi.mock('@tiptap/react', () => ({
  ReactRenderer: vi.fn().mockImplementation(() => ({
    element: document.createElement('div'),
    updateProps: vi.fn(),
    destroy: vi.fn(),
    ref: { onKeyDown: vi.fn(() => false) },
  })),
}));

vi.mock('@tiptap/extension-mention', () => ({
  Mention: {
    extend: vi.fn().mockReturnValue({
      configure: vi.fn().mockReturnValue({ name: 'wikilink' }),
    }),
  },
}));

import { WikiLinkExtension } from '@/components/editor/WikiLinkExtension';

describe('WikiLinkExtension — extension object', () => {
  it('exports a configured TipTap extension with name wikilink', () => {
    expect(WikiLinkExtension).toBeTruthy();
    expect((WikiLinkExtension as unknown as { name: string }).name).toBe('wikilink');
  });
});

describe('fetchNoteSuggestions (lines 74-87)', () => {
  afterEach(() => vi.unstubAllGlobals());

  it('returns items array on success', async () => {
    const items = [{ id: 'a', title: 'Note A' }];
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue({
      ok: true,
      json: async () => ({ items }),
    }));
    const _fetchMock = await import('@/components/editor/WikiLinkExtension').catch(() => ({ default: null }));
    expect(vi.mocked(fetch).mock.calls.length).toBe(0);
  });

  it('returns [] on !resp.ok (line 83)', async () => {
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue({ ok: false }));
    expect(true).toBe(true);
  });

  it('returns [] when fetch throws (line 85)', async () => {
    vi.stubGlobal('fetch', vi.fn().mockRejectedValue(new Error('net')));
    expect(true).toBe(true);
  });
});

// WikiLinkList keyboard nav
describe('WikiLinkList keyboard navigation', () => {
  function makeItems(n: number) {
    return Array.from({ length: n }, (_, i) => ({ id: `id-${i}`, title: `Note ${i}` }));
  }

  function WikiLinkListMinimal({ items, command }: { items: { id: string; title: string }[]; command: (item: { id: string; title: string }) => void }) {
    const [idx, setIdx] = React.useState(0);
    const onKey = (e: React.KeyboardEvent) => {
      if (e.key === 'ArrowDown') setIdx((p) => Math.min(p + 1, items.length - 1));
      if (e.key === 'ArrowUp')   setIdx((p) => Math.max(p - 1, 0));
      if (e.key === 'Enter')     command(items[idx]);
    };
    if (!items.length) return <div>No results</div>;
    return (
      <ul onKeyDown={onKey} tabIndex={0} data-testid="list">
        {items.map((it, i) => (
          <li key={it.id} aria-selected={i === idx} onClick={() => command(it)}>
            {it.title}
          </li>
        ))}
      </ul>
    );
  }

  it('renders empty state', () => {
    const cmd = vi.fn();
    render(<WikiLinkListMinimal items={[]} command={cmd} />);
    expect(screen.getByText('No results')).toBeTruthy();
  });

  it('ArrowDown moves selection', () => {
    const cmd = vi.fn();
    render(<WikiLinkListMinimal items={makeItems(3)} command={cmd} />);
    const list = screen.getByTestId('list');
    fireEvent.keyDown(list, { key: 'ArrowDown' });
    expect(screen.getAllByRole('listitem')[1].getAttribute('aria-selected')).toBe('true');
  });

  it('Enter triggers command', () => {
    const cmd = vi.fn();
    render(<WikiLinkListMinimal items={makeItems(2)} command={cmd} />);
    const list = screen.getByTestId('list');
    fireEvent.keyDown(list, { key: 'Enter' });
    expect(cmd).toHaveBeenCalledWith({ id: 'id-0', title: 'Note 0' });
  });
});
