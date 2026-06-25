import { describe, it, expect, vi } from 'vitest';
import { render, screen } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import AIChatPage from '../AIChatPage';

// Stub the heavy AIChat component so the test focuses on the page shell.
vi.mock('../../components/AIChat', () => ({
  default: () => <div data-testid="ai-chat-inner">AI Chat Stub</div>,
}));

describe('AIChatPage', () => {
  it('renders the AiChat component', () => {
    render(<MemoryRouter><AIChatPage /></MemoryRouter>);
    // The page wrapper has data-testid="ai-chat" (set on the outer div in AIChatPage.tsx)
    expect(screen.getByTestId('ai-chat')).toBeInTheDocument();
  });

  it('renders the page heading', () => {
    render(<MemoryRouter><AIChatPage /></MemoryRouter>);
    expect(screen.getByText('AI Chat')).toBeInTheDocument();
  });
});
