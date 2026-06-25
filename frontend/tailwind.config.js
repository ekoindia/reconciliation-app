/** @type {import('tailwindcss').Config} */
export default {
  content: ["./index.html", "./src/**/*.{js,jsx}"],
  theme: {
    extend: {
      colors: {
        // Brand petrol-teal. DEFAULT/light/dark are load-bearing — referenced
        // throughout the pages — so their values never change; the numeric
        // scale is additive for finer-grained design work.
        primary: {
          DEFAULT: "#094053",
          light: "#0F5A72",
          dark: "#062D3A",
          50: "#EDF6F9",
          100: "#D7EAF1",
          200: "#ABD4E2",
          300: "#7CB9CE",
          400: "#4A94B0",
          500: "#1E7090",
          600: "#115A75",
          700: "#094053",
          800: "#062D3A",
          900: "#041F29",
          950: "#02131A",
        },
        // Brand amber accent.
        accent: {
          DEFAULT: "#F9AB10",
          light: "#FBBC38",
          50: "#FEF8E8",
          100: "#FDEFC8",
          200: "#FBDD8C",
          300: "#FBCA50",
          400: "#FABA2C",
          500: "#F9AB10",
          600: "#DB920A",
          700: "#B77607",
          800: "#935C08",
          900: "#7A4B0C",
        },
        surface: { DEFAULT: "#f8f9fc", dark: "#f1f3f8" },
      },
      fontFamily: {
        sans: [
          "Inter",
          "ui-sans-serif",
          "system-ui",
          "-apple-system",
          "Segoe UI",
          "Roboto",
          "Helvetica Neue",
          "Arial",
          "sans-serif",
        ],
        mono: [
          "JetBrains Mono",
          "ui-monospace",
          "SFMono-Regular",
          "Menlo",
          "Consolas",
          "monospace",
        ],
      },
      boxShadow: {
        card: "0 1px 2px 0 rgb(16 24 40 / 0.04), 0 1px 3px 0 rgb(16 24 40 / 0.06)",
        "card-hover":
          "0 4px 6px -2px rgb(16 24 40 / 0.05), 0 12px 16px -4px rgb(16 24 40 / 0.10)",
        soft: "0 2px 4px -2px rgb(16 24 40 / 0.06), 0 4px 8px -2px rgb(16 24 40 / 0.08)",
      },
      keyframes: {
        // Opacity-only on purpose: a `transform` here (even translateY(0)) with
        // fill-mode `both` leaves a non-`none` transform on every
        // `.animate-fade-in` element forever, making it the containing block for
        // any descendant `position:fixed` modal and clipping it to the content
        // area instead of the viewport. Keeping this transform-free fixes that at
        // the root for ALL modals (App's page wrapper uses animate-fade-in).
        "fade-in": {
          from: { opacity: "0" },
          to: { opacity: "1" },
        },
        shimmer: {
          "100%": { transform: "translateX(100%)" },
        },
      },
      animation: {
        "fade-in": "fade-in 0.25s ease-out both",
      },
    },
  },
  plugins: [],
}
