/** @type {import('tailwindcss').Config} */
export default {
  content: [
    "./index.html",
    "./src/**/*.{vue,js,ts,jsx,tsx}",
  ],
  theme: {
    extend: {
      colors: {
        // Dark theme colors inspired by the reference image
        'game-bg': '#0f0f23',
        'game-dark': '#1a1a2e',
        'game-card': '#16213e',
        'game-border': '#2d3561',
        'game-accent': '#7c3aed',
        'game-accent-light': '#a78bfa',
        'wolf-red': '#ef4444',
        'good-green': '#22c55e',
        'seer-cyan': '#06b6d4',
        'witch-purple': '#a855f7',
        'guard-blue': '#3b82f6',
        'hunter-orange': '#f97316',
      },
      fontFamily: {
        'game': ['Inter', 'system-ui', 'sans-serif'],
      },
      animation: {
        'pulse-slow': 'pulse 3s cubic-bezier(0.4, 0, 0.6, 1) infinite',
        'float': 'float 6s ease-in-out infinite',
      },
      keyframes: {
        float: {
          '0%, 100%': { transform: 'translateY(0px)' },
          '50%': { transform: 'translateY(-10px)' },
        }
      }
    },
  },
  plugins: [],
}
