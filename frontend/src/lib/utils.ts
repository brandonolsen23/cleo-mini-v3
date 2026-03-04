import { clsx, type ClassValue } from "clsx";
import { twMerge } from "tailwind-merge";

export function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs));
}

/** Format large numbers with abbreviations (1200 -> "1.2k") */
export function formatCompact(n: number): string {
  if (n >= 1_000_000) return `${(n / 1_000_000).toFixed(1)}M`;
  if (n >= 1_000) return `${(n / 1_000).toFixed(1)}k`;
  return n.toLocaleString();
}

/** Format currency (CAD) */
export function formatCurrency(n: number): string {
  return new Intl.NumberFormat("en-CA", {
    style: "currency",
    currency: "CAD",
    maximumFractionDigits: 0,
  }).format(n);
}

/** Format percentage with sign */
export function formatPercent(n: number): string {
  const sign = n > 0 ? "+" : "";
  return `${sign}${n.toFixed(1)}%`;
}

/** Title-case a string ("MAIN STREET" → "Main Street") */
export function titleCase(s: string): string {
  return s
    .toLowerCase()
    .replace(/\b\w/g, (c) => c.toUpperCase());
}

const SUFFIX_ABBR: Record<string, string> = {
  STREET: "St",
  AVENUE: "Ave",
  ROAD: "Rd",
  DRIVE: "Dr",
  BOULEVARD: "Blvd",
  CRESCENT: "Cres",
  COURT: "Crt",
  PLACE: "Pl",
  LANE: "Ln",
  CIRCLE: "Cir",
  TRAIL: "Trl",
  TERRACE: "Terr",
  HIGHWAY: "Hwy",
  PARKWAY: "Pkwy",
  CONCESSION: "Con",
};

const DIR_ABBR: Record<string, string> = {
  NORTH: "N",
  SOUTH: "S",
  EAST: "E",
  WEST: "W",
  NORTHEAST: "NE",
  NORTHWEST: "NW",
  SOUTHEAST: "SE",
  SOUTHWEST: "SW",
};

/** Format a street name: title case + abbreviate suffixes/directions.
 *  Pass a full address to strip city/province (everything after first comma). */
export function formatStreet(address: string): string {
  const street = address.split(",")[0];
  return street
    .split(/\s+/)
    .map((w) => {
      const upper = w.toUpperCase();
      if (SUFFIX_ABBR[upper]) return SUFFIX_ABBR[upper];
      if (DIR_ABBR[upper]) return DIR_ABBR[upper];
      return titleCase(w);
    })
    .join(" ");
}

/** Format ISO date string (YYYY-MM-DD) as "Feb 20, 2026" */
export function formatDate(iso: string): string {
  if (!iso) return "";
  const d = new Date(iso + "T00:00:00");
  if (isNaN(d.getTime())) return iso;
  const mon = d.toLocaleString("en-US", { month: "short" });
  return `${mon} ${d.getDate()}, ${d.getFullYear()}`;
}
