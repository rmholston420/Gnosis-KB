import React from 'react';
import ReactDOM from 'react-dom/client';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import App from './App';
import './index.css';

// Gnosis is a dark-mode-only app. Tailwind's darkMode:'class' requires the
// .dark class to be present on <html> for dark: variants to activate.
// Without this, text-text-primary resolves to near-black on dark surfaces.
document.documentElement.classList.add('dark');

const queryClient = new QueryClient({
  defaultOptions: { queries: { staleTime: 30_000, retry: 1 } },
});

ReactDOM.createRoot(document.getElementById('root')!).render(
  <React.StrictMode>
    <QueryClientProvider client={queryClient}>
      <App />
    </QueryClientProvider>
  </React.StrictMode>,
);
