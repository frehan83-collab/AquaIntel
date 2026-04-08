import type { Config } from "tailwindcss";

const config: Config = {
  content: [
    "./src/pages/**/*.{js,ts,jsx,tsx,mdx}",
    "./src/components/**/*.{js,ts,jsx,tsx,mdx}",
    "./src/app/**/*.{js,ts,jsx,tsx,mdx}",
  ],
  darkMode: "class",
  theme: {
    extend: {
      colors: {
        ocean: {
          50: "#E6F9F7",
          100: "#B3EDE8",
          200: "#80E1D9",
          300: "#4DD5CA",
          400: "#1AC9BB",
          500: "#00D4C8",
          600: "#00A89F",
          700: "#007D77",
          800: "#00524F",
          900: "#0A1A2F",
          950: "#060F1C",
        },
        glass: {
          light: "rgba(255, 255, 255, 0.06)",
          medium: "rgba(255, 255, 255, 0.10)",
          border: "rgba(255, 255, 255, 0.08)",
        },
        salmon: {
          DEFAULT: "#E8734A",
          50: "#FDF2EE",
          100: "#FADDD3",
          200: "#F5BBA7",
          300: "#F09A7B",
          400: "#E8734A",
          500: "#D4582E",
          600: "#B04424",
          700: "#8C351C",
        },
        fjord: {
          surface: "#1A2942",
          midwater: "#0F1D30",
          abyss: "#060F1C",
        },
        kelp: {
          DEFAULT: "#2D7A6F",
          light: "#3A9B8E",
          dark: "#1F5C53",
        },
        ice: {
          DEFAULT: "#E8EDF2",
          warm: "#F0F4F8",
        },
        data: {
          biomass: '#F59E0B',
          lice: '#F43F5E',
          temperature: '#3B82F6',
          mortality: '#9F1239',
          feeding: '#059669',
          oxygen: '#06B6D4',
        },
        traffic: {
          green: '#22C55E',
          yellow: '#EAB308',
          red: '#EF4444',
        },
        chart: {
          1: '#00D4C8',
          2: '#E8734A',
          3: '#8B5CF6',
          4: '#F59E0B',
          5: '#EC4899',
          6: '#10B981',
          7: '#6366F1',
          8: '#14B8A6',
        },
        surface: {
          0: '#060F1C',
          1: '#0A1629',
          2: '#0F1D33',
          3: '#152640',
          4: '#1A2F4D',
        },
      },
      fontFamily: {
        sans: ["var(--font-sans)", "DM Sans", "-apple-system", "BlinkMacSystemFont", "Segoe UI", "sans-serif"],
        display: ["var(--font-display)", "DM Serif Display", "Georgia", "serif"],
        mono: ["var(--font-mono)", "JetBrains Mono", "Fira Code", "monospace"],
      },
      boxShadow: {
        glass: "0 8px 32px rgba(0,0,0,0.3), inset 0 1px 0 rgba(255,255,255,0.05)",
        glow: "0 0 30px rgba(0,212,200,0.2)",
        "glow-sm": "0 0 16px rgba(0,212,200,0.15)",
        "glow-lg": "0 0 48px rgba(0,212,200,0.25)",
        "glow-salmon": "0 0 30px rgba(232,115,74,0.2)",
        "glow-salmon-sm": "0 0 16px rgba(232,115,74,0.15)",
        panel: "0 8px 32px rgba(0,0,0,0.3), inset 0 1px 0 rgba(255,255,255,0.03), inset 0 -1px 2px rgba(0,0,0,0.2)",
      },
      animation: {
        "pulse-slow": "pulse 3s cubic-bezier(0.4,0,0.6,1) infinite",
        float: "float 6s ease-in-out infinite",
        "shimmer": "shimmer 2s linear infinite",
      },
      keyframes: {
        float: {
          "0%, 100%": { transform: "translateY(0)" },
          "50%": { transform: "translateY(-6px)" },
        },
        shimmer: {
          "0%": { transform: "translateX(-100%)" },
          "100%": { transform: "translateX(100%)" },
        },
      },
      borderRadius: {
        "2xl": "16px",
        "3xl": "20px",
      },
    },
  },
  plugins: [],
};
export default config;
