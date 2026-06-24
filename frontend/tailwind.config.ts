import type { Config } from 'tailwindcss';

/**
 * Wrap a CSS variable reference so Tailwind can inject the alpha channel.
 * e.g. withAlpha('--gnosis-accent') → 'rgb(var(--gnosis-accent-rgb) / <alpha-value>)'
 * Since we're using hex CSS vars, we use the simpler form and rely on
 * `color-mix` for opacity — just reference the var directly.
 */
function v(varName: string) {
  return `var(${varName})`;
}

const config: Config = {
  content: ['./index.html', './src/**/*.{js,ts,jsx,tsx}'],
  darkMode: ['attribute', 'data-theme'],
  theme: {
    extend: {
      colors: {
        // ---- Legacy bg/text/accent scale (kept for compatibility) ----
        bg: {
          primary:   'var(--color-bg)',
          secondary: 'var(--color-surface)',
          tertiary:  'var(--color-surface-2)',
          elevated:  'var(--color-surface-dynamic)',
        },
        border: {
          DEFAULT: 'var(--color-border)',
          subtle:  'var(--color-divider)',
          muted:   'var(--color-text-faint)',
        },
        text: {
          primary:   'var(--color-text)',
          secondary: 'var(--color-text-muted)',
          muted:     'var(--color-text-faint)',
          link:      'var(--color-primary)',
        },
        accent: {
          blue:   '#1f6feb',
          green:  '#238636',
          orange: '#d18616',
          red:    '#da3633',
          purple: '#8957e5',
          cyan:   '#0e7490',
        },
        note: {
          permanent: '#58a6ff',
          fleeting:  '#3fb950',
          literature:'#d2a8ff',
          journal:   '#ffa657',
          map:       '#79c0ff',
          reference: '#f78166',
          project:   '#e3b341',
        },

        // ---- gnosis-* semantic tokens — now CSS variable–backed so they
        //      respond to the data-theme light/dark toggle. ----
        gnosis: {
          bg:         v('--gnosis-bg'),
          surface:    v('--gnosis-surface'),
          border:     v('--gnosis-border'),
          hover:      v('--gnosis-hover'),
          fg:         v('--gnosis-fg'),
          muted:      v('--gnosis-muted'),
          accent:     v('--gnosis-accent'),
          'accent-2': v('--gnosis-accent-2'),
          error:      v('--gnosis-error'),
          success:    v('--gnosis-success'),
        },
      },
      fontFamily: {
        sans:  ['Inter',          'system-ui', 'sans-serif'],
        mono:  ['JetBrains Mono', 'Fira Code', 'monospace'],
        serif: ['Crimson Pro',    'Georgia',   'serif'],
      },
      spacing: {
        sidebar:      '260px',
        'sidebar-sm': '48px',
      },
      borderRadius: {
        sm:      '4px',
        DEFAULT: '6px',
        lg:      '8px',
        xl:      '12px',
      },
      boxShadow: {
        sm: 'var(--shadow-sm)',
        md: 'var(--shadow-md)',
        lg: 'var(--shadow-lg)',
      },
      animation: {
        'fade-in':   'fadeIn  0.15s ease-out',
        'slide-in':  'slideIn 0.2s  ease-out',
        'spin-slow': 'spin 2s linear infinite',
        'pulse':     'pulse 2s cubic-bezier(0.4,0,0.6,1) infinite',
        'shimmer':   'shimmer 1.5s ease-in-out infinite',
      },
      keyframes: {
        fadeIn: {
          '0%':   { opacity: '0' },
          '100%': { opacity: '1' },
        },
        slideIn: {
          '0%':   { transform: 'translateX(-10px)', opacity: '0' },
          '100%': { transform: 'translateX(0)',     opacity: '1' },
        },
        shimmer: {
          '0%':   { backgroundPosition: '-200% 0' },
          '100%': { backgroundPosition: '200% 0' },
        },
      },
    },
  },
  plugins: [],
};

export default config;
