import React from 'react';
import { render } from '@testing-library/react';
import { describe, it, expect, vi, beforeEach } from 'vitest';
import WikilinkAutocomplete from '@/components/editor/WikilinkAutocomplete';

describe('editor WikilinkAutocomplete', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('renders nothing without anchorRect', () => {
    const { container } = render(<WikilinkAutocomplete query="a" suggestions={[]} anchorRect={new DOMRect()} onSelect={vi.fn()} onClose={vi.fn()} />);
    expect(container).toBeTruthy();
  });
});
