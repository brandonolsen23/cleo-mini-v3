import { useMemo } from "react";

/** CSS variable names for chart theming. */
export const CHART_VARS = {
  primary: "--jade-9",
  secondary: "--slate-8",
  positive: "--green-9",
  negative: "--red-9",
  grid: "--slate-4",
  text: "--slate-11",
  tooltipBg: "--slate-12",
  tooltipText: "--slate-1",
} as const;

/** Fallback hex values (light theme) used during SSR or when vars unresolvable. */
const FALLBACKS: Record<keyof typeof CHART_VARS, string> = {
  primary: "#29a383",
  secondary: "#6b7280",
  positive: "#30a46c",
  negative: "#e5484d",
  grid: "#d1d5db",
  text: "#4b5563",
  tooltipBg: "#1e293b",
  tooltipText: "#f8fafc",
};

function resolveVar(varName: string, fallback: string): string {
  if (typeof document === "undefined") return fallback;
  const raw = getComputedStyle(document.documentElement).getPropertyValue(varName).trim();
  return raw || fallback;
}

export interface ChartColors {
  primary: string;
  secondary: string;
  positive: string;
  negative: string;
  grid: string;
  text: string;
  tooltipBg: string;
  tooltipText: string;
}

/**
 * Hook that resolves Radix CSS variables to computed color strings
 * that Recharts can use directly (it needs actual color values, not var() refs).
 */
export function useChartColors(): ChartColors {
  return useMemo(() => {
    const result = {} as ChartColors;
    for (const [key, varName] of Object.entries(CHART_VARS)) {
      result[key as keyof ChartColors] = resolveVar(varName, FALLBACKS[key as keyof typeof FALLBACKS]);
    }
    return result;
  }, []);
}
