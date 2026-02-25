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
        // Core 2 shade scale — remapped to Radix slate
        shade: {
          "01": "var(--slate-12)",
          "02": "var(--slate-12)",
          "03": "var(--slate-12)",
          "04": "var(--slate-11)",
          "05": "var(--slate-10)",
          "06": "var(--slate-9)",
          "07": "var(--slate-8)",
          "08": "var(--slate-6)",
          "09": "var(--slate-3)",
          "10": "var(--slate-1)",
        },
        // Core 2 background tokens — remapped to Radix
        b: {
          surface1: "var(--slate-2)",
          surface2: "var(--color-panel-solid)",
          surface3: "var(--slate-1)",
          highlight: "var(--slate-3)",
          pop: "var(--jade-9)",
          dark1: "var(--slate-12)",
          dark2: "var(--slate-12)",
          depth: "var(--slate-12)",
          depth2: "var(--slate-2)",
        },
        // Core 2 text tokens — remapped to Radix
        t: {
          primary: "var(--slate-12)",
          secondary: "var(--slate-11)",
          tertiary: "var(--slate-9)",
          light: "var(--slate-1)",
        },
        // Core 2 stroke tokens — remapped to Radix
        s: {
          DEFAULT: "var(--slate-6)",
          strong: "var(--slate-7)",
          subtle: "var(--slate-4)",
          stroke2: "var(--slate-7)",
          highlight: "var(--slate-8)",
          focus: "var(--jade-9)",
        },
        // Core 2 primary scale — remapped to Radix jade
        "primary-01": "var(--jade-11)",
        "primary-02": "var(--jade-10)",
        "primary-03": "var(--jade-9)",
        "primary-04": "var(--jade-7)",
        "primary-05": "var(--jade-3)",
        // Core 2 secondary scale — remapped to Radix slate
        "secondary-01": "var(--slate-10)",
        "secondary-02": "var(--slate-9)",
        "secondary-03": "var(--slate-8)",
        "secondary-04": "var(--slate-6)",
        "secondary-05": "var(--slate-3)",
        // Core 2 accent — remapped to Radix jade
        blue: {
          DEFAULT: "var(--jade-9)",
          light: "var(--jade-3)",
          dark: "var(--jade-11)",
        },
        green: {
          DEFAULT: "var(--green-9)",
          light: "var(--green-3)",
        },
        red: {
          DEFAULT: "var(--red-9)",
          light: "var(--red-3)",
        },
        orange: {
          DEFAULT: "var(--orange-9)",
          light: "var(--orange-3)",
        },
        purple: {
          DEFAULT: "var(--purple-9)",
          light: "var(--purple-3)",
        },
        // Radix accent utilities
        "accent-color": "var(--accent-9)",
        "accent-subtle": "var(--accent-3)",
        // shadcn semantic tokens — remapped to Radix via CSS vars
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
        "slide-in-from-right": {
          from: { transform: "translateX(100%)" },
          to: { transform: "translateX(0)" },
        },
        "slide-out-to-right": {
          from: { transform: "translateX(0)" },
          to: { transform: "translateX(100%)" },
        },
        "overlay-in": {
          from: { opacity: "0" },
          to: { opacity: "1" },
        },
        "overlay-out": {
          from: { opacity: "1" },
          to: { opacity: "0" },
        },
      },
      animation: {
        "accordion-down": "accordion-down 0.2s ease-out",
        "accordion-up": "accordion-up 0.2s ease-out",
        "slide-in-from-right": "slide-in-from-right 0.3s ease-out",
        "slide-out-to-right": "slide-out-to-right 0.2s ease-in",
        "overlay-in": "overlay-in 0.3s ease-out",
        "overlay-out": "overlay-out 0.2s ease-in",
      },
    },
  },
  plugins: [require("tailwindcss-animate")],
};
