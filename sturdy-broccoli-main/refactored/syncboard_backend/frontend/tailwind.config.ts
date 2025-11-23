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
        primary: {
          DEFAULT: '#00d4ff',
          dark: '#00b8e6',
        },
        accent: {
          purple: '#a78bfa',
          green: '#4ade80',
          orange: '#f59e0b',
          red: '#ef4444',
          blue: '#60a5fa',
        },
        dark: {
          DEFAULT: '#0a0a0a',
          100: '#1a1a1a',
          200: '#2a2a2a',
          300: '#333333',
          400: '#444444',
        },
      },
    },
  },
  plugins: [],
};

export default config;
