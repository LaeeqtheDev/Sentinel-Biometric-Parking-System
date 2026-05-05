import type { Config } from 'tailwindcss';

const config: Config = {
  content: [
    './src/pages/**/*.{js,ts,jsx,tsx,mdx}',
    './src/components/**/*.{js,ts,jsx,tsx,mdx}',
    './src/app/**/*.{js,ts,jsx,tsx,mdx}',
  ],
  theme: {
    extend: {
      colors: {
        // Background layers
        ink: {
          950: '#08080a',
          900: '#0d0d11',
          800: '#13131a',
          700: '#1b1b25',
          600: '#26262f',
          500: '#3a3a47',
        },
        // Foreground / text
        bone: {
          50: '#f5f5f7',
          200: '#d4d4d8',
          400: '#9a9aa3',
          500: '#71717a',
        },
        // Primary accent - amber/yellow (parking attention vibe)
        amber: {
          DEFAULT: '#fbbf24',
          glow: '#fde047',
          deep: '#f59e0b',
        },
        // Status colors
        granted: '#34d399',
        denied: '#f87171',
        pending: '#a3a3a3',
      },
      fontFamily: {
        display: ['var(--font-display)', 'Georgia', 'serif'],
        sans: ['var(--font-sans)', 'system-ui', 'sans-serif'],
        mono: ['var(--font-mono)', 'ui-monospace', 'monospace'],
      },
      animation: {
        'pulse-soft': 'pulse-soft 3s ease-in-out infinite',
        'scan': 'scan 2.5s ease-in-out infinite',
        'gate-open': 'gate-open 1.2s cubic-bezier(0.65, 0, 0.35, 1) forwards',
        'fade-up': 'fade-up 0.5s ease-out forwards',
      },
      keyframes: {
        'pulse-soft': {
          '0%, 100%': { opacity: '0.7' },
          '50%': { opacity: '1' },
        },
        'scan': {
          '0%, 100%': { transform: 'translateY(0%)' },
          '50%': { transform: 'translateY(100%)' },
        },
        'gate-open': {
          '0%': { transform: 'rotate(0deg)' },
          '100%': { transform: 'rotate(-85deg)' },
        },
        'fade-up': {
          '0%': { opacity: '0', transform: 'translateY(8px)' },
          '100%': { opacity: '1', transform: 'translateY(0)' },
        },
      },
      backgroundImage: {
        'grid-pattern':
          'linear-gradient(to right, rgba(255,255,255,0.03) 1px, transparent 1px), linear-gradient(to bottom, rgba(255,255,255,0.03) 1px, transparent 1px)',
      },
      backgroundSize: {
        'grid-sm': '24px 24px',
      },
    },
  },
  plugins: [],
};

export default config;
