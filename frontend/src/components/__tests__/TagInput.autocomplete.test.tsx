import React from 'react';
import { render, screen } from '@testing-library/react';
import { describe, it, expect, vi, beforeEach } from 'vitest';

import TagInput from '@/components/TagInput';

describe('TagInput.autocomplete', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('renders input', () => {
    render(<TagInput tags={[]} onChange={vi.fn()} />);
    expect(screen.getByRole('textbox')).toBeTruthy();
  });
});
