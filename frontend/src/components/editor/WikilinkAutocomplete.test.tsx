import React from 'react';
import { renderHook } from '@testing-library/react';
import { describe, it, expect, vi, beforeEach } from 'vitest';
import { useWikilinkDetector } from '@/components/editor/WikilinkAutocomplete';

describe('WikilinkAutocomplete hook', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('exposes anchorRect', () => {
    const { result } = renderHook(() => useWikilinkDetector());
    const { wikilinkQuery, anchorRect, insertWikilink } = result.current;
    expect(wikilinkQuery).toBeNull();
    expect(anchorRect).toBeNull();
    expect(typeof insertWikilink).toBe('function');
  });
});
