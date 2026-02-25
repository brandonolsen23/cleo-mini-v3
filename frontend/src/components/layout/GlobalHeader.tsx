import { useCallback, useEffect, useRef, useState } from "react";
import { useLocation } from "react-router-dom";
import { useSearch } from "@/api/search";
import SearchResults from "./SearchResults";

/* Core 2 SVG icon paths (24x24 viewBox) */
const ICON_SEARCH =
  "M12.948 3.93c3.939 0 7.133 3.193 7.133 7.133s-3.193 7.133-7.133 7.133c-1.697 0-3.256-.593-4.48-1.583L5.21 19.871A.75.75 0 0 1 4.15 18.81l3.256-3.257c-.995-1.226-1.591-2.789-1.591-4.491 0-3.939 3.193-7.133 7.133-7.133zm0 1.5c-3.111 0-5.633 2.522-5.633 5.633s2.522 5.633 5.633 5.633 5.633-2.522 5.633-5.633-2.522-5.633-5.633-5.633z";
const ICON_BELL =
  "M13 3.25A5.75 5.75 0 0 1 18.75 9v6A2.75 2.75 0 0 1 16 17.75H8A2.75 2.75 0 0 1 5.25 15V9A5.75 5.75 0 0 1 11 3.25h2zm0 1.5h-2A4.25 4.25 0 0 0 6.75 9v6A1.25 1.25 0 0 0 8 16.25h8A1.25 1.25 0 0 0 17.25 15V9A4.25 4.25 0 0 0 13 4.75zm1 14.5a.75.75 0 1 1 0 1.5h-4a.75.75 0 1 1 0-1.5h4z";
const ICON_CHAT =
  "M11.999 3.9c4.771 0 8.669 3.508 8.669 7.877s-3.898 7.877-8.669 7.877a9.35 9.35 0 0 1-3.669-.747l.245.098-3.944 1.058a.75.75 0 0 1-.938-.821l.02-.098.878-3.278-.146-.224c-.669-1.077-1.053-2.287-1.109-3.549l-.007-.316c0-4.369 3.898-7.877 8.669-7.877zm0 1.5c-3.976 0-7.169 2.873-7.169 6.377 0 1.259.413 2.465 1.179 3.5a.75.75 0 0 1 .122.641l-.634 2.361 2.933-.786a.75.75 0 0 1 .394.001l.094.033a7.85 7.85 0 0 0 3.081.627c3.976 0 7.169-2.873 7.169-6.377S15.975 5.4 11.999 5.4z";
const ICON_CLOSE =
  "M6.881 5.82l5.126 5.126 5.126-5.126a.75.75 0 0 1 1.061 1.061l-5.126 5.127 5.126 5.126a.75.75 0 0 1-1.061 1.061l-5.127-5.126-5.127 5.126a.75.75 0 0 1-1.061-1.061l5.126-5.126L5.82 6.88A.75.75 0 0 1 6.881 5.82z";

function SvgIcon({ d, className }: { d: string; className?: string }) {
  return (
    <svg
      className={`inline-flex size-6 ${className ?? ""}`}
      width={24}
      height={24}
      viewBox="0 0 24 24"
    >
      <path d={d} />
    </svg>
  );
}

const pageTitles: Record<string, string> = {
  "/dashboard": "Welcome, Brandon.",
  "/transactions": "Transactions",
  "/properties": "Properties",
  "/parties": "Companies",
  "/contacts": "Contacts",
  "/brands": "Brands",
  "/map": "Map",
  "/keywords": "Keywords",
};

function usePageTitle(): string {
  const { pathname } = useLocation();
  // Exact match first, then prefix match for detail pages
  if (pageTitles[pathname]) return pageTitles[pathname];
  const base = "/" + pathname.split("/")[1];
  return pageTitles[base] ?? "";
}

export default function GlobalHeader() {
  const [query, setQuery] = useState("");
  const [open, setOpen] = useState(false);
  const inputRef = useRef<HTMLInputElement>(null);
  const wrapperRef = useRef<HTMLDivElement>(null);
  const pageTitle = usePageTitle();

  const { results } = useSearch(query);
  const hasQuery = query.trim().length >= 2;

  useEffect(() => {
    setOpen(hasQuery);
  }, [hasQuery]);

  // Cmd+K / Ctrl+K to focus
  useEffect(() => {
    function handleKeyDown(e: KeyboardEvent) {
      if ((e.metaKey || e.ctrlKey) && e.key === "k") {
        e.preventDefault();
        inputRef.current?.focus();
      }
    }
    document.addEventListener("keydown", handleKeyDown);
    return () => document.removeEventListener("keydown", handleKeyDown);
  }, []);

  // Close on click outside
  useEffect(() => {
    function handleClick(e: MouseEvent) {
      if (wrapperRef.current && !wrapperRef.current.contains(e.target as Node)) {
        setOpen(false);
      }
    }
    document.addEventListener("mousedown", handleClick);
    return () => document.removeEventListener("mousedown", handleClick);
  }, []);

  const handleClose = useCallback(() => {
    setOpen(false);
    setQuery("");
    inputRef.current?.blur();
  }, []);

  const handleClear = useCallback(() => {
    setQuery("");
    inputRef.current?.focus();
  }, []);

  return (
    <header className="sticky top-0 z-30 flex h-[5.5rem] items-center bg-white/40 backdrop-blur-md px-6 border-b border-white/40">
      {/* Page title */}
      <div className="mr-auto text-h4 text-[var(--slate-12)]">{pageTitle}</div>

      {/* Search */}
      <div ref={wrapperRef} className="relative">
        <div
          className={`relative w-[19.75rem] rounded-3xl overflow-hidden transition-shadow ${
            open ? "z-[100] shadow-depth" : ""
          }`}
        >
          <button className="group absolute top-3 left-3 z-10 text-[0]">
            <SvgIcon
              d={ICON_SEARCH}
              className="fill-[var(--slate-9)] transition-colors group-hover:fill-[var(--slate-12)]"
            />
          </button>
          <input
            ref={inputRef}
            type="text"
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            onFocus={() => hasQuery && setOpen(true)}
            onKeyDown={(e) => {
              if (e.key === "Escape") handleClose();
            }}
            placeholder="Search anything..."
            className={`w-full h-12 pl-[2.625rem] border rounded-3xl text-body-2 text-[var(--slate-12)] placeholder:text-[var(--slate-9)] outline-none bg-white/70 border-white/60 ${
              query ? "pr-[2.625rem]" : "pr-2.5"
            }`}
            autoComplete="off"
          />
          <button
            className={`group absolute top-3 right-3 z-10 text-[0] transition-all ${
              query ? "visible opacity-100" : "invisible opacity-0"
            }`}
            onClick={handleClear}
          >
            <SvgIcon
              d={ICON_CLOSE}
              className="fill-[var(--slate-9)] transition-colors group-hover:fill-[var(--slate-12)]"
            />
          </button>
        </div>

        {open && <SearchResults results={results} onClose={handleClose} />}
      </div>

      {/* Icon buttons */}
      <div className="flex items-center gap-3 ml-3">
        <button className="inline-flex items-center justify-center w-12 h-12 rounded-full bg-white/60 fill-[var(--slate-11)] transition-all hover:fill-[var(--slate-12)] hover:bg-white/80 hover:shadow-[0_2px_8px_rgba(0,0,0,0.06)]">
          <SvgIcon d={ICON_BELL} />
        </button>
        <button className="inline-flex items-center justify-center w-12 h-12 rounded-full bg-white/60 fill-[var(--slate-11)] transition-all hover:fill-[var(--slate-12)] hover:bg-white/80 hover:shadow-[0_2px_8px_rgba(0,0,0,0.06)]">
          <SvgIcon d={ICON_CHAT} />
        </button>
        <div className="w-12 h-12 rounded-full bg-white/70 flex items-center justify-center overflow-hidden">
          <svg className="size-6 fill-[var(--slate-9)]" width={24} height={24} viewBox="0 0 24 24">
            <circle cx="12" cy="8" r="4" />
            <path d="M20 19c0-3.314-3.582-6-8-6s-8 2.686-8 6" />
          </svg>
        </div>
      </div>
    </header>
  );
}
