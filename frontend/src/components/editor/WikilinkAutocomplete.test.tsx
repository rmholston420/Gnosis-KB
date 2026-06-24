import React from 'react';
import { renderHook } from '@testing-library/react';
import { describe, it, expect, vi, beforeEach } from 'vitest';
import { useWikilinkDetector } from '@/components/editor/WikilinkAutocomplete';

describe('WikilinkAutocomplete hook', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('exposes wikilinkQuery and anchorRect as null initially', () => {
    const textarea = document.createElement('textarea');
    const ref = { current: textarea } as React.RefObject<HTMLTextAreaElement>;
    const { result } = renderHook(() => useWikilinkDetector(ref, '', vi.fn()));
    expect(result.current.wikilinkQuery).toBeNull();
    expect(result.current.anchorRect).toBeNull();
  });
});
