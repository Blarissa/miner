import colors from 'tailwindcss/colors'

/** @type {import('tailwindcss').Config} */
export default {
  content: [
    "./index.html",
    "./src/**/*.{js,ts,jsx,tsx}",
  ],
  theme: {
    extend: {
      colors: {
        // Semantic tokens mapped onto the stock Tailwind scales already used
        // by convention across the app: cyan = primary/accent action,
        // rose = danger/destructive, emerald = success, amber = warning,
        // slate = neutral. Using e.g. `bg-primary-600` is visually identical
        // to `bg-cyan-600` today, but makes the convention explicit and
        // discoverable in config instead of implicit in class strings.
        primary: colors.cyan,
        danger: colors.rose,
        success: colors.emerald,
        warning: colors.amber,
        neutral: colors.slate,
      },
      keyframes: {
        // Landing page: código Java rolando para cima (conteúdo duplicado => loop contínuo).
        'code-scroll': {
          '0%': { transform: 'translateY(0)' },
          '100%': { transform: 'translateY(-50%)' },
        },
        // Tags de métricas surgindo e sumindo em ciclo.
        'badge-cycle': {
          '0%, 8%': { opacity: '0', transform: 'translateY(8px) scale(0.95)' },
          '18%, 85%': { opacity: '1', transform: 'translateY(0) scale(1)' },
          '95%, 100%': { opacity: '0', transform: 'translateY(-4px) scale(0.98)' },
        },
      },
      animation: {
        'code-scroll': 'code-scroll 14s linear infinite',
        'badge-cycle': 'badge-cycle 6s ease-in-out infinite both',
      },
    },
  },
  plugins: [],
}
