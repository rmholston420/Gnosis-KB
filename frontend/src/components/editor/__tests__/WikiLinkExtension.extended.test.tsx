import React from 'react';
import { describe, it, expect, vi } from 'vitest';

vi.mock('@tiptap/react', () => ({
  ReactRenderer: vi.fn().mockImplementation((_Component: any, { props }: any) => {
    const self = {
      element: document.createElement('div'),
      ref: { onKeyDown: vi.fn(() => true) },
      updateProps: vi.fn(),
      destroy: vi.fn(),
      props,
    };
    return self;
  }),
}));

describe('WikiLinkExtension.extended', () => {
  it('loads module', async () => {
    const mod = await import('@/components/editor/WikiLinkExtension');
    expect(mod).toBeTruthy();
  });
});
