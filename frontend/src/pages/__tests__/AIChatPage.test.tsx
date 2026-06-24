/**
 * AIChatPage.test.tsx
 * ===================
 * AIChatPage is a thin shell that renders the <AiChat> component.
 */
import { describe, it, expect, vi } from 'vitest';
import { render, screen } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import AIChatPage from '../AIChatPage';

// Stub heavy AiChat to keep this suite fast and focused
vi.mock('../../components/ai/AiChat', () => ({ default: () => <div data-testid="ai-chat" /> }));

describe('AIChatPage', () => {
  it('renders without crashing', () => {
    render(<MemoryRouter><AIChatPage /></MemoryRouter>);
    expect(document.body).toBeInTheDocument();
  });

  it('renders the AiChat component', () => {
    render(<MemoryRouter><AIChatPage /></MemoryRouter>);
    expect(screen.getByTestId('ai-chat')).toBeInTheDocument();
  });
});
