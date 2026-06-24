/**
 * AiChat.test.tsx
 * ===============
 * Tests for the streaming AI chat panel component.
 * We mock the global EventSource (SSE) so the component can open connections
 * without a real server.  fetch is also stubbed for URL-building paths.
 */
import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import AiChat from '../AiChat';

const mockNavigate = vi.fn();
vi.mock('react-router-dom', async () => {
  const actual = await vi.importActual<typeof import('react-router-dom')>('react-router-dom');
  return { ...actual, useNavigate: () => mockNavigate };
});

// ---------------------------------------------------------------------------
// EventSource stub — controls SSE lifecycle in tests
// ---------------------------------------------------------------------------
class MockEventSource {
  url: string;
  onmessage: ((e: MessageEvent) => void) | null = null;
  onerror:   ((e: Event) => void) | null = null;
  onopen:    ((e: Event) => void) | null = null;
  readyState = 0;
  static CONNECTING = 0;
  static OPEN = 1;
  static CLOSED = 2;
  static instances: MockEventSource[] = [];

  constructor(url: string) {
    this.url = url;
    MockEventSource.instances.push(this);
  }
  close() { this.readyState = MockEventSource.CLOSED; }
  addEventListener = vi.fn();
  removeEventListener = vi.fn();
  dispatchEvent = vi.fn();
}

function renderChat() {
  return render(<MemoryRouter><AiChat /></MemoryRouter>);
}

beforeEach(() => {
  mockNavigate.mockReset();
  vi.restoreAllMocks();
  MockEventSource.instances = [];
  // @ts-expect-error — replace global EventSource with test stub
  global.EventSource = MockEventSource;
});

describe('AiChat', () => {
  it('renders the message input', () => {
    renderChat();
    expect(screen.getByPlaceholderText(/ask/i)).toBeInTheDocument();
  });

  it('renders the Send button', () => {
    renderChat();
    expect(screen.getByRole('button', { name: /send/i })).toBeInTheDocument();
  });

  it('Send button is disabled when input is empty', () => {
    renderChat();
    expect(screen.getByRole('button', { name: /send/i })).toBeDisabled();
  });

  it('Send button is enabled when input has text', () => {
    renderChat();
    const input = screen.getByPlaceholderText(/ask/i);
    fireEvent.change(input, { target: { value: 'What is emptiness?' } });
    expect(screen.getByRole('button', { name: /send/i })).not.toBeDisabled();
  });

  it('renders RAG mode selector buttons', () => {
    renderChat();
    expect(screen.getByText(/hybrid/i)).toBeInTheDocument();
  });

  it('shows empty chat state when no messages', () => {
    renderChat();
    // The bot-icon empty state is shown; no assistant message div yet
    expect(screen.getByText(/ask anything/i)).toBeInTheDocument();
  });

  it('shows user message bubble after sending', async () => {
    renderChat();
    const input = screen.getByPlaceholderText(/ask/i);
    fireEvent.change(input, { target: { value: 'What is emptiness?' } });
    fireEvent.click(screen.getByRole('button', { name: /send/i }));
    await waitFor(() =>
      expect(screen.getByText('What is emptiness?')).toBeInTheDocument()
    );
  });

  it('clears input after sending', async () => {
    renderChat();
    const input = screen.getByPlaceholderText(/ask/i) as HTMLInputElement;
    fireEvent.change(input, { target: { value: 'Hello' } });
    fireEvent.click(screen.getByRole('button', { name: /send/i }));
    await waitFor(() => expect(input.value).toBe(''));
  });

  it('opens an EventSource connection after sending', async () => {
    renderChat();
    fireEvent.change(screen.getByPlaceholderText(/ask/i), {
      target: { value: 'What is karma?' },
    });
    fireEvent.click(screen.getByRole('button', { name: /send/i }));
    await waitFor(() => expect(MockEventSource.instances.length).toBeGreaterThan(0));
    expect(MockEventSource.instances[0].url).toContain('stream/chat');
  });

  it('EventSource URL contains the message query param', async () => {
    renderChat();
    fireEvent.change(screen.getByPlaceholderText(/ask/i), {
      target: { value: 'explain shunyata' },
    });
    fireEvent.click(screen.getByRole('button', { name: /send/i }));
    await waitFor(() => expect(MockEventSource.instances.length).toBeGreaterThan(0));
    expect(MockEventSource.instances[0].url).toContain('message=explain+shunyata');
  });

  it('renders Clear button', () => {
    renderChat();
    expect(screen.getByRole('button', { name: /clear/i })).toBeInTheDocument();
  });
});
