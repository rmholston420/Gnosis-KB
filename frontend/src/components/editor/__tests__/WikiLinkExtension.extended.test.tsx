import { describe, it, expect, vi } from 'vitest';

vi.mock('@tiptap/react', () => ({
  ReactRenderer: vi.fn().mockImplementation(
    (_Component: unknown, { props }: { props: Record<string, unknown> }) => ({
      element: document.createElement('div'),
      ref: { onKeyDown: vi.fn(() => true) },
      updateProps: vi.fn(),
      destroy: vi.fn(),
      props,
    })
  ),
}));

describe('WikiLinkExtension.extended', () => {
  it('loads module', async () => {
    const mod = await import('@/components/editor/WikiLinkExtension');
    expect(mod).toBeTruthy();
  });
});
