/** @type {import('tailwindcss').Config} */
export default {
  darkMode: ["class"],
  content: ["./index.html", "./src/**/*.{ts,tsx}"],
  theme: {
    extend: {
      fontFamily: {
        sans: ['"Geist Variable"', "sans-serif"],
        mono: ['"Geist Mono Variable"', "monospace"],
      },
      // Core 2 typography scale
      fontSize: {
        // caption: 12px
        caption: ["0.75rem", { lineHeight: "1.6", letterSpacing: "-0.02em" }],
        // body-2: 14px
        "body-2": ["0.875rem", { lineHeight: "1.5", letterSpacing: "-0.025em" }],
        // body-1: 16px
        "body-1": ["1rem", { lineHeight: "1.5", letterSpacing: "-0.015em" }],
        // button: 14px/600
        button: ["0.875rem", { lineHeight: "1", letterSpacing: "-0.015em", fontWeight: "600" }],
        // sub-title-1: 16px/600
        "sub-title-1": ["1rem", { lineHeight: "1.5", letterSpacing: "-0.015em", fontWeight: "600" }],
        // sub-title-2: 14px/700
        "sub-title-2": ["0.875rem", { lineHeight: "1.55", letterSpacing: "-0.015em", fontWeight: "700" }],
        // overline: 10px/500
        overline: ["0.625rem", { lineHeight: "1", letterSpacing: "0.02em", fontWeight: "500" }],
        // h6: 20px/600
        h6: ["1.25rem", { lineHeight: "1.45", letterSpacing: "-0.01em", fontWeight: "600" }],
        // h5: 24px/500
        h5: ["1.5rem", { lineHeight: "1.45", letterSpacing: "-0.01em", fontWeight: "500" }],
        // h4: 32px/600
        h4: ["2rem", { lineHeight: "1.45", letterSpacing: "0.003em", fontWeight: "600" }],
        // h3: 48px/500
        h3: ["3rem", { lineHeight: "1.25", fontWeight: "500" }],
        // h2: 60px/500
        h2: ["3.75rem", { lineHeight: "1.25", letterSpacing: "-0.015em", fontWeight: "500" }],
      },
      letterSpacing: {
        tighter: "-0.025em",
        tight: "-0.015em",
        snug: "-0.01em",
        normal: "0em",
      },
      spacing: {
        "1.75": "0.4375rem",
        "4.5": "1.125rem",
        "6.5": "1.625rem",
        "7": "1.75rem",
        "10.5": "2.625rem",
        "22": "5.5rem",
        "67.5": "16.875rem",
        "79": "19.75rem",
        "85": "21.25rem",
        "18": "4.5rem",
        "74": "18.5rem",
        "106.5": "26.625rem",
      },
      borderRadius: {
        sm: "0.25rem",
        md: "0.375rem",
        lg: "0.5rem",
        xl: "0.75rem",
        "2xl": "1rem",
        "3xl": "1.5rem",
        "4xl": "2rem",
      },
      colors: {
        // Core 2 shade scale
        shade: {
          "01": "#141414",
          "02": "#101010",
          "03": "#1a1a1a",
          "04": "#262626",
          "05": "#404040",
          "06": "#727272",
          "07": "#a1a1a1",
          "08": "#e2e2e2",
          "09": "#f1f1f1",
          "10": "#fdfdfd",
        },
        // Core 2 background tokens
        b: {
          surface1: "#f1f1f1",
          surface2: "#fdfdfd",
          surface3: "#ffffff",
          highlight: "#f9f9f9",
          pop: "#2a85ff",
          dark1: "#141414",
          dark2: "#1a1a1a",
          depth: "#101010",
          depth2: "#f5f5f5",
        },
        // Core 2 text tokens
        t: {
          primary: "#101010",
          secondary: "#727272",
          tertiary: "#a1a1a1",
          light: "#fdfdfd",
        },
        // Core 2 stroke tokens
        s: {
          DEFAULT: "#e2e2e2",
          strong: "#d4d4d4",
          subtle: "#f1f1f1",
          stroke2: "#d4d4d4",
          highlight: "#a1a1a1",
          focus: "#2a85ff",
        },
        // Core 2 primary scale
        "primary-01": "#0045b5",
        "primary-02": "#1a6fdd",
        "primary-03": "#2a85ff",
        "primary-04": "#6ab0ff",
        "primary-05": "#e8f1ff",
        // Core 2 secondary scale
        "secondary-01": "#404040",
        "secondary-02": "#727272",
        "secondary-03": "#a1a1a1",
        "secondary-04": "#e2e2e2",
        "secondary-05": "#f1f1f1",
        // Core 2 accent
        blue: {
          DEFAULT: "#2a85ff",
          light: "#e8f1ff",
          dark: "#1a6fdd",
        },
        green: {
          DEFAULT: "#83bf6e",
          light: "#eafae4",
        },
        red: {
          DEFAULT: "#ff6a55",
          light: "#ffeeeb",
        },
        orange: {
          DEFAULT: "#ff9f38",
          light: "#fff4e6",
        },
        purple: {
          DEFAULT: "#8e59ff",
          light: "#f0e8ff",
        },
        // shadcn semantic tokens (remapped to Core 2 via CSS vars)
        border: "hsl(var(--border))",
        input: "hsl(var(--input))",
        ring: "hsl(var(--ring))",
        background: "hsl(var(--background))",
        foreground: "hsl(var(--foreground))",
        primary: {
          DEFAULT: "hsl(var(--primary))",
          foreground: "hsl(var(--primary-foreground))",
        },
        secondary: {
          DEFAULT: "hsl(var(--secondary))",
          foreground: "hsl(var(--secondary-foreground))",
        },
        destructive: {
          DEFAULT: "hsl(var(--destructive))",
          foreground: "hsl(var(--destructive-foreground))",
        },
        muted: {
          DEFAULT: "hsl(var(--muted))",
          foreground: "hsl(var(--muted-foreground))",
        },
        accent: {
          DEFAULT: "hsl(var(--accent))",
          foreground: "hsl(var(--accent-foreground))",
        },
        popover: {
          DEFAULT: "hsl(var(--popover))",
          foreground: "hsl(var(--popover-foreground))",
        },
        card: {
          DEFAULT: "hsl(var(--card))",
          foreground: "hsl(var(--card-foreground))",
        },
      },
      boxShadow: {
        widget:
          "0px 2px 4px rgba(0, 0, 0, 0.04), 0px 0px 0px 1px rgba(0, 0, 0, 0.04)",
        depth:
          "0px 8px 24px rgba(0, 0, 0, 0.06), 0px 0px 0px 1px rgba(0, 0, 0, 0.04)",
        dropdown:
          "0px 16px 48px rgba(0, 0, 0, 0.1), 0px 0px 0px 1px rgba(0, 0, 0, 0.04)",
        "input-typing":
          "0px 0px 0px 2px #2a85ff",
        "depth-toggle":
          "0px 4px 12px rgba(0, 0, 0, 0.06), 0px 0px 0px 1px rgba(0, 0, 0, 0.03)",
      },
      keyframes: {
        "accordion-down": {
          from: { height: "0" },
          to: { height: "var(--radix-accordion-content-height)" },
        },
        "accordion-up": {
          from: { height: "var(--radix-accordion-content-height)" },
          to: { height: "0" },
        },
      },
      animation: {
        "accordion-down": "accordion-down 0.2s ease-out",
        "accordion-up": "accordion-up 0.2s ease-out",
      },
    },
  },
  plugins: [require("tailwindcss-animate")],
};
