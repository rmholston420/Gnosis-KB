import type { Config } from 'tailwindcss';

const config: Config = {
  content: ['./index.html', './src/**/*.{js,ts,jsx,tsx}'],
  darkMode: 'class',
  theme: {
    extend: {
      colors: {
        // Gnosis dark theme palette
        bg: {
          primary: '#0d1117',
          secondary: '#161b22',
          tertiary: '#21262d',
          elevated: '#2d333b',
        },
        border: {
          DEFAULT: '#30363d',
          subtle: '#21262d',
          muted: '#484f58',
        },
        text: {
          primary: '#e6edf3',
          secondary: '#8b949e',
          muted: '#6e7681',
          link: '#58a6ff',
        },
        accent: {
          blue: '#1f6feb',
          green: '#238636',
          orange: '#d18616',
          red: '#da3633',
          purple: '#8957e5',
          cyan: '#0e7490',
        },
        note: {
          permanent: '#58a6ff',
          fleeting: '#3fb950',
          literature: '#d2a8ff',
          journal: '#ffa657',
          map: '#79c0ff',
          reference: '#f78166',
          project: '#e3b341',
        },
      },
      fontFamily: {
        sans: ['Inter', 'system-ui', 'sans-serif'],
        mono: ['JetBrains Mono', 'Fira Code', 'monospace'],
        serif: ['Crimson Pro', 'Georgia', 'serif'],
      },
      spacing: {
        sidebar: '260px',
        'sidebar-sm': '48px',
      },
      borderRadius: {
        sm: '4px',
        DEFAULT: '6px',
        lg: '8px',
        xl: '12px',
      },
      animation: {
        'fade-in': 'fadeIn 0.15s ease-out',
        'slide-in': 'slideIn 0.2s ease-out',
        'spin-slow': 'spin 2s linear infinite',
      },
      keyframes: {
        fadeIn: {
          '0%': { opacity: '0' },
          '100%': { opacity: '1' },
        },
        slideIn: {
          '0%': { transform: 'translateX(-10px)', opacity: '0' },
          '100%': { transform: 'translateX(0)', opacity: '1' },
        },
      },
    },
  },
  plugins: [],
};

export default config;
