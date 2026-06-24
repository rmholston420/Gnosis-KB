/**
 * ThemeToggle — icon button that switches between dark and light themes.
 * Reads/writes `data-theme` on <html> and persists to localStorage.
 */
import React, { useEffect, useState } from 'react';
import { Moon, Sun } from 'lucide-react';

type Theme = 'dark' | 'light';

function getInitialTheme(): Theme {
  const saved = localStorage.getItem('gnosis-theme');
  if (saved === 'light') return 'light';
  if (saved === 'dark')  return 'dark';
  return window.matchMedia('(prefers-color-scheme: dark)').matches ? 'dark' : 'light';
}

function applyTheme(theme: Theme) {
  document.documentElement.setAttribute('data-theme', theme);
  localStorage.setItem('gnosis-theme', theme);
}

/**
 * ThemeToggle renders a Sun/Moon icon button.
 * Dark mode is the default (Gnosis uses a dark-first design).
 */
export function ThemeToggle({ className }: { className?: string }) {
  const [theme, setTheme] = useState<Theme>(getInitialTheme);

  useEffect(() => { applyTheme(theme); }, [theme]);

  const toggle = () => setTheme((t) => (t === 'dark' ? 'light' : 'dark'));

  return (
    <button
      onClick={toggle}
      aria-label={`Switch to ${theme === 'dark' ? 'light' : 'dark'} theme`}
      className={`p-1.5 rounded-md text-gnosis-muted hover:text-gnosis-fg hover:bg-gnosis-hover transition-colors ${className ?? ''}`}
    >
      {theme === 'dark' ? <Sun size={15} /> : <Moon size={15} />}
    </button>
  );
}
