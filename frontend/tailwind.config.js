/** @type {import('tailwindcss').Config} */
export default {
  content: ["./index.html", "./src/**/*.{js,ts,jsx,tsx}"],
  theme: {
    fontFamily: {
      sans: ['"Untitled Sans"', "-apple-system", "BlinkMacSystemFont", '"Segoe UI"', "Helvetica", "Arial", "sans-serif"],
    },
    /*
     * WorkOS weight mapping: their "bold" is Untitled Sans Medium (500).
     * Remap Tailwind's semibold and bold so every component inherits
     * the correct weight without per-file overrides.
     *
     *   font-normal   → 400 (Regular)  — body text, inactive nav
     *   font-medium   → 500 (Medium)   — emphasis, headings, active nav
     *   font-semibold → 500 (Medium)   — remapped (same as medium)
     *   font-bold     → 500 (Medium)   — remapped (same as medium)
     */
    fontWeight: {
      light: "300",
      normal: "400",
      medium: "500",
      semibold: "500",
      bold: "500",
    },
  },
  plugins: [],
};
