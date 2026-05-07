/** @type {import('tailwindcss').Config} */
module.exports = {
  content: ['./src/**/*.{js,jsx,ts,tsx}'],
  darkMode: 'class',
  theme: {
    extend: {
      colors: {
        surface: {
          primary: 'var(--bg-primary)',
          secondary: 'var(--bg-secondary)',
          card: 'var(--bg-card)',
          elevated: 'var(--bg-elevated)',
        },
        accent: {
          cyan: 'var(--accent-cyan)',
          red: 'var(--accent-red)',
          amber: 'var(--accent-amber)',
          green: 'var(--accent-green)',
          blue: 'var(--accent-blue)',
          gold: 'var(--accent-gold)',
          purple: 'var(--accent-purple)',
        },
        border: {
          DEFAULT: 'var(--border)',
          bright: 'var(--border-bright)',
        },
        iob: {
          gold: '#F59E0B',
          'gold-dark': '#D97706',
          'gold-light': '#FBBF24',
          purple: '#8B5CF6',
          'purple-dark': '#7C3AED',
          'purple-light': '#A78BFA',
        },
      },
      fontFamily: {
        display: ['IBM Plex Sans', 'system-ui', '-apple-system', 'sans-serif'],
        mono: ['IBM Plex Mono', 'ui-monospace', 'monospace'],
      },
      backdropBlur: {
        glass: '12px',
      },
      borderRadius: {
        DEFAULT: '12px',
        lg: '16px',
      },
      animation: {
        'fade-in-up': 'fadeInUp 0.4s ease both',
        'pulse-glow': 'pulseGlow 2s ease-in-out infinite',
        shimmer: 'shimmer 2s linear infinite',
        'slide-in-right': 'slideInRight 0.4s ease both',
        'gold-pulse': 'goldPulse 3s ease-in-out infinite',
      },
      keyframes: {
        fadeInUp: {
          from: { opacity: '0', transform: 'translateY(20px)' },
          to: { opacity: '1', transform: 'translateY(0)' },
        },
        pulseGlow: {
          '0%, 100%': { boxShadow: '0 0 4px rgba(239,68,68,0.3)' },
          '50%': { boxShadow: '0 0 12px rgba(239,68,68,0.6)' },
        },
        shimmer: {
          '0%': { backgroundPosition: '-200% 0' },
          '100%': { backgroundPosition: '200% 0' },
        },
        slideInRight: {
          from: { opacity: '0', transform: 'translateX(30px)' },
          to: { opacity: '1', transform: 'translateX(0)' },
        },
        goldPulse: {
          '0%, 100%': { boxShadow: '0 0 8px rgba(245,158,11,0.2)' },
          '50%': { boxShadow: '0 0 24px rgba(245,158,11,0.4)' },
        },
      },
    },
  },
  plugins: [],
};
