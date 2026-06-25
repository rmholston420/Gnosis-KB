import React from 'react';
import { render, type RenderOptions } from '@testing-library/react';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { MemoryRouter } from 'react-router-dom';

/**
 * Creates a fresh QueryClient per test (no shared state between tests).
 */
// eslint-disable-next-line react-refresh/only-export-components
export function makeQueryClient() {
  return new QueryClient({
    defaultOptions: {
      queries: { retry: false, gcTime: 0 },
      mutations: { retry: false },
    },
  });
}

interface WrapperProps {
  children: React.ReactNode;
  initialEntries?: string[];
}

/**
 * Wraps children in the providers every component needs:
 * QueryClientProvider + MemoryRouter
 */
export function AllProviders({ children, initialEntries = ['/'] }: WrapperProps) {
  const qc = makeQueryClient();
  return (
    <QueryClientProvider client={qc}>
      <MemoryRouter initialEntries={initialEntries}>{children}</MemoryRouter>
    </QueryClientProvider>
  );
}

/**
 * Custom render that automatically wraps in AllProviders.
 * Accepts an optional `initialEntries` array to simulate routing.
 */
// eslint-disable-next-line react-refresh/only-export-components
export function renderWithProviders(
  ui: React.ReactElement,
  options?: RenderOptions & { initialEntries?: string[] },
) {
  const { initialEntries, ...rest } = options ?? {};
  return render(ui, {
    wrapper: ({ children }) => (
      <AllProviders initialEntries={initialEntries}>{children}</AllProviders>
    ),
    ...rest,
  });
}

// eslint-disable-next-line react-refresh/only-export-components
export * from '@testing-library/react';
