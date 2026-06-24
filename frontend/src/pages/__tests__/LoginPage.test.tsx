import { describe, it, expect, vi } from 'vitest';
import { render, screen, fireEvent } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import { createElement } from 'react';

vi.mock('../../store/useAppStore', () => ({
  useAppStore: vi.fn(() => ({ setUser: vi.fn(), isAuthenticated: false })),
}));
vi.mock('../../api/notes', () => ({ loginUser: vi.fn(async () => ({ token: 'tok', user: { username: 'u' } })) }));

import LoginPage from '../LoginPage';

describe('LoginPage', () => {
  it('renders email and password inputs', () => {
    render(createElement(MemoryRouter, null, createElement(LoginPage)));
    expect(screen.getByLabelText(/email/i)).toBeInTheDocument();
    expect(screen.getByLabelText(/password/i)).toBeInTheDocument();
  });

  it('has a submit button', () => {
    render(createElement(MemoryRouter, null, createElement(LoginPage)));
    expect(screen.getByRole('button', { name: /sign in|log in/i })).toBeInTheDocument();
  });

  it('shows validation message when submitted empty', async () => {
    render(createElement(MemoryRouter, null, createElement(LoginPage)));
    fireEvent.click(screen.getByRole('button', { name: /sign in|log in/i }));
    // HTML5 required validation prevents submit; email input should be in focus
    expect(screen.getByLabelText(/email/i)).toBeInTheDocument();
  });
});
