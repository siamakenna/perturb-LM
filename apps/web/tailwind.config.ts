import type { Config } from "tailwindcss";

const config: Config = {
  content: ["./src/**/*.{ts,tsx}"],
  theme: {
    extend: {
      colors: {
        ink: "#142136",
        paper: "#f7f4ee",
        mist: "#ece7dc",
        teal: "#1f8a83",
        violet: "#6a5ad7",
      },
      boxShadow: {
        soft: "0 24px 80px rgba(20, 33, 54, 0.10)",
      },
      fontFamily: {
        sans: ["var(--font-geist-sans)", "Inter", "ui-sans-serif", "system-ui"],
        mono: ["var(--font-geist-mono)", "SFMono-Regular", "Menlo", "monospace"],
      },
    },
  },
  plugins: [],
};

export default config;
