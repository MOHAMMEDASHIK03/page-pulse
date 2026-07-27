/** @type {import('tailwindcss').Config} */
export default {
  content: ["./index.html", "./src/**/*.{ts,tsx}"],
  theme: {
    extend: {
      colors: {
        ink: {
          950: "#05070A",
          900: "#0B0F14",
          800: "#111720",
          700: "#1A222E",
          600: "#26313F",
        },
        pulse: {
          400: "#5CFFC4",
          500: "#26E6A0",
          600: "#0FBF85",
        },
        signal: {
          amber: "#FFB020",
          rose: "#FF5C7A",
        },
      },
      fontFamily: {
        display: ["'Space Grotesk'", "sans-serif"],
        body: ["'Inter'", "sans-serif"],
        mono: ["'JetBrains Mono'", "monospace"],
      },
      boxShadow: {
        glass: "0 8px 32px 0 rgba(0, 0, 0, 0.45)",
        "glow-pulse": "0 0 24px 0 rgba(38, 230, 160, 0.35)",
      },
      backgroundImage: {
        "grid-fade":
          "linear-gradient(rgba(38,230,160,0.06) 1px, transparent 1px), linear-gradient(90deg, rgba(38,230,160,0.06) 1px, transparent 1px)",
      },
      keyframes: {
        "pulse-line": {
          "0%": { strokeDashoffset: "1000" },
          "100%": { strokeDashoffset: "0" },
        },
        blip: {
          "0%, 100%": { opacity: "0.4" },
          "50%": { opacity: "1" },
        },
        "fade-up": {
          "0%": { opacity: "0", transform: "translateY(12px)" },
          "100%": { opacity: "1", transform: "translateY(0)" },
        },
      },
      animation: {
        "pulse-line": "pulse-line 2.4s linear infinite",
        blip: "blip 2s ease-in-out infinite",
        "fade-up": "fade-up 0.5s ease-out both",
      },
    },
  },
  plugins: [],
};
