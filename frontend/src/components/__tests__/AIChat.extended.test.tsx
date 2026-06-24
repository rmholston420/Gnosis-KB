import React from 'react';
import { render, screen } from '@testing-library/react';
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';

vi.mock('@/services/api', () => ({
  default: {
    aiChat: vi.fn().mockResolvedValue({ response: 'ok' }),
  },
}));

import AIChat from '@/components/AIChat';

describe('AIChat.extended', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  afterEach(() => {
    vi.unstubAllGlobals();
  });

  it('renders chat input', () => {
    render(<AIChat />);
    expect(screen.getByRole('textbox')).toBeTruthy();
  });
});
