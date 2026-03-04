/**
 * WorkOS Dashboard Design System — Theme Configuration
 *
 * This file is the single source of truth for design decisions.
 * Components should reference these constants, not hardcode values.
 *
 * Typography:
 *   Font: Untitled Sans (Klim Type Foundry), same as WorkOS dashboard.
 *   Weights: 400 (Regular) for body, 500 (Medium) for emphasis/headings.
 *   WorkOS never uses 700 (Bold) in their UI — their "bold" is Medium.
 *   Tailwind's font-bold and font-semibold are remapped to 500 in tailwind.config.js.
 *
 * Colors:
 *   Gray scale: Radix "slate" — use --gray-N tokens, never hardcode hex/rgba.
 *   Accent: Radix "jade" — use --accent-N or --jade-N tokens.
 *   Semantic: --green-11 (positive), --red-11 (negative).
 *
 * Spacing:
 *   Card padding: p-5 (20px) standard.
 *   Section gaps: gap-6 (24px) between major sections, gap-4 (16px) within.
 *
 * Borders:
 *   Card border: border border-[var(--gray-6)] rounded-[var(--card-radius)]
 *   Subtle divider: border-[var(--gray-4)]
 *   --card-radius: 12px (defined in index.css :root)
 */

/** Radix Theme provider props — change accentColor to re-theme everything */
export const THEME = {
  accentColor: "jade" as const,
  grayColor: "slate" as const,
  radius: "medium" as const,
  scaling: "100%" as const,
} as const;

/** Chart color palette — uses Radix CSS vars so they adapt to theme changes */
export const CHART_COLORS = {
  /** Primary series (darkest to lightest) */
  primary: [
    "var(--jade-11)",
    "var(--jade-9)",
    "var(--jade-7)",
    "var(--jade-4)",
  ],
  /** Single-color accent for simple charts */
  accent: "var(--accent-9)",
  /** Semantic trend colors */
  positive: "var(--green-11)",
  negative: "var(--red-11)",
  neutral: "var(--gray-8)",
} as const;

/**
 * Brand category → Radix color mapping.
 * Used everywhere a category badge appears (detail page, map popups, etc.).
 * Keys are lowercase to match API values. Fallback is "gray".
 */
const CATEGORY_COLORS: Record<string, RadixColor> = {
  grocery: "lime",
  qsr: "orange",
  "big-box retail": "blue",
  "specialty retail": "plum",
  "discount retail": "amber",
  "full-service": "violet",
  "take-out": "pink",
  automotive: "tomato",
  "financial services": "cyan",
  fuel: "indigo",
};

type RadixColor =
  | "lime" | "orange" | "blue" | "plum" | "amber"
  | "violet" | "pink" | "tomato" | "cyan" | "indigo"
  | "gray";

/** Return the Radix color for a brand category. */
export function categoryColor(category: string): RadixColor {
  return CATEGORY_COLORS[category.toLowerCase()] ?? "gray";
}
