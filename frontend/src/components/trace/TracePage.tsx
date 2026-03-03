import { useState, useRef, useEffect } from "react";
import { useSearchParams } from "react-router-dom";
import { useTrace, useTraceSearch } from "@/api/trace";
import type { TraceResult, SearchResult } from "@/api/trace";

/* ------------------------------------------------------------------ */
/* Stage definitions — order matters                                   */
/* ------------------------------------------------------------------ */

const STAGE_ORDER = [
  "ingest",
  "parsed",
  "normalized",
  "expanded",
  "geocoded",
  "property",
  "parcel",
  "compiled",
] as const;

type StageName = (typeof STAGE_ORDER)[number];

const STAGE_META: Record<StageName, { label: string; color: string; description: string }> = {
  ingest:     { label: "Ingest",     color: "bg-slate-100 text-slate-700",   description: "Raw HTML tracking" },
  parsed:     { label: "Parsed",     color: "bg-amber-50 text-amber-700",    description: "Extracted from HTML" },
  normalized: { label: "Normalized", color: "bg-blue-50 text-blue-700",      description: "Decomposed & standardized" },
  expanded:   { label: "Expanded",   color: "bg-indigo-50 text-indigo-700",  description: "Compound-split, geocodable" },
  geocoded:   { label: "Geocoded",   color: "bg-green-50 text-green-700",    description: "Coordinates from Mapbox" },
  property:   { label: "Property",   color: "bg-purple-50 text-purple-700",  description: "Canonical registry entry (legacy)" },
  parcel:     { label: "Parcel",     color: "bg-orange-50 text-orange-700",  description: "Boundary & assessment" },
  compiled:   { label: "Compiled",   color: "bg-emerald-50 text-emerald-700", description: "All stages reassembled" },
};

/* ------------------------------------------------------------------ */
/* Search bar                                                          */
/* ------------------------------------------------------------------ */

function SearchBar({
  onSelect,
  initialValue,
}: {
  onSelect: (id: string) => void;
  initialValue?: string;
}) {
  const [query, setQuery] = useState(initialValue ?? "");
  const { results, searching, search } = useTraceSearch();
  const [open, setOpen] = useState(false);
  const ref = useRef<HTMLDivElement>(null);
  const debounce = useRef<ReturnType<typeof setTimeout>>();

  // Close dropdown on outside click
  useEffect(() => {
    function handle(e: MouseEvent) {
      if (ref.current && !ref.current.contains(e.target as Node)) setOpen(false);
    }
    document.addEventListener("mousedown", handle);
    return () => document.removeEventListener("mousedown", handle);
  }, []);

  function handleChange(val: string) {
    setQuery(val);
    clearTimeout(debounce.current);
    debounce.current = setTimeout(() => {
      search(val);
      setOpen(true);
    }, 250);
  }

  function handleSelect(r: SearchResult) {
    setQuery(r.id);
    setOpen(false);
    onSelect(r.id);
  }

  function handleKeyDown(e: React.KeyboardEvent) {
    if (e.key === "Enter") {
      e.preventDefault();
      setOpen(false);
      if (query.trim()) onSelect(query.trim());
    }
  }

  return (
    <div ref={ref} className="relative w-full max-w-xl">
      <div className="flex gap-2">
        <input
          type="text"
          value={query}
          onChange={(e) => handleChange(e.target.value)}
          onKeyDown={handleKeyDown}
          onFocus={() => results.length > 0 && setOpen(true)}
          placeholder="RT196880, GW00001, BR_00045, or search by address..."
          className="flex-1 px-4 py-2.5 bg-white rounded-xl border border-gray-200 text-sm focus:outline-none focus:ring-2 focus:ring-blue-200 focus:border-blue-400"
        />
        <button
          onClick={() => query.trim() && onSelect(query.trim())}
          className="px-5 py-2.5 bg-gray-900 text-white text-sm font-medium rounded-xl hover:bg-gray-800 transition-colors"
        >
          Trace
        </button>
      </div>
      {open && results.length > 0 && (
        <div className="absolute z-50 top-full mt-1 w-full bg-white rounded-xl border border-gray-200 shadow-lg max-h-64 overflow-auto">
          {results.map((r) => (
            <button
              key={r.id}
              onClick={() => handleSelect(r)}
              className="w-full text-left px-4 py-2.5 text-sm hover:bg-gray-50 border-b border-gray-100 last:border-0"
            >
              <span className="font-mono text-gray-900">{r.id}</span>
              {r.label !== r.id && (
                <span className="ml-2 text-gray-500">
                  {r.label.replace(`${r.id} — `, "")}
                </span>
              )}
              <span className={`ml-2 text-[10px] uppercase font-medium px-1.5 py-0.5 rounded ${
                r.source === "realtrack" ? "bg-amber-100 text-amber-700" :
                r.source === "geowarehouse" ? "bg-teal-100 text-teal-700" :
                "bg-violet-100 text-violet-700"
              }`}>
                {r.source}
              </span>
            </button>
          ))}
          {searching && (
            <div className="px-4 py-2 text-xs text-gray-400">Searching...</div>
          )}
        </div>
      )}
    </div>
  );
}

/* ------------------------------------------------------------------ */
/* Stage timeline — horizontal flow indicator                          */
/* ------------------------------------------------------------------ */

function StageTimeline({ stages }: { stages: Record<string, unknown> }) {
  return (
    <div className="flex items-center gap-1 flex-wrap">
      {STAGE_ORDER.map((name, i) => {
        const present = name in stages;
        const meta = STAGE_META[name];
        return (
          <div key={name} className="flex items-center">
            {i > 0 && (
              <div className={`w-6 h-px mx-0.5 ${present ? "bg-gray-300" : "bg-gray-200"}`} />
            )}
            <a
              href={`#stage-${name}`}
              className={`px-3 py-1.5 rounded-lg text-xs font-medium transition-colors ${
                present
                  ? `${meta.color} ring-1 ring-inset ring-gray-200`
                  : "bg-gray-50 text-gray-300"
              }`}
            >
              {meta.label}
              {!present && " --"}
            </a>
          </div>
        );
      })}
    </div>
  );
}

/* ------------------------------------------------------------------ */
/* Field renderers                                                     */
/* ------------------------------------------------------------------ */

function FieldValue({ value }: { value: unknown }) {
  if (value === null || value === undefined) return <span className="text-gray-300">--</span>;
  if (value === "") return <span className="text-gray-300 italic">empty</span>;
  if (typeof value === "boolean") return <span className={value ? "text-green-600" : "text-gray-400"}>{String(value)}</span>;
  if (typeof value === "number") {
    // Preserve full precision for coordinates/floats, use locale formatting for integers
    const display = Number.isInteger(value) ? value.toLocaleString() : String(value);
    return <span className="text-gray-900 tabular-nums">{display}</span>;
  }
  if (typeof value === "string") return <span className="text-gray-900">{value}</span>;
  if (Array.isArray(value)) {
    if (value.length === 0) return <span className="text-gray-300">[]</span>;
    // Flat arrays (strings/numbers)
    if (value.every((v) => typeof v === "string" || typeof v === "number")) {
      return <span className="text-gray-900">{value.join(", ")}</span>;
    }
    // Array of objects — render each
    return (
      <div className="space-y-2 mt-1">
        {value.map((item, idx) => (
          <div key={idx} className="bg-gray-50/50 rounded-lg p-2 border border-gray-100">
            <div className="text-[10px] text-gray-400 font-mono mb-1">[{idx}]</div>
            <FieldTable data={item} />
          </div>
        ))}
      </div>
    );
  }
  if (typeof value === "object") {
    return <FieldTable data={value as Record<string, unknown>} />;
  }
  return <span className="text-gray-600">{String(value)}</span>;
}

function FieldTable({ data }: { data: Record<string, unknown> }) {
  const entries = Object.entries(data);
  if (entries.length === 0) return <span className="text-gray-300">empty object</span>;

  return (
    <div className="space-y-0">
      {entries.map(([key, val]) => {
        const isNested = (typeof val === "object" && val !== null && !Array.isArray(val)) ||
                         (Array.isArray(val) && val.length > 0 && typeof val[0] === "object");
        return (
          <div key={key} className={isNested ? "py-1.5" : "flex gap-3 py-1 items-baseline"}>
            <span className="text-[11px] font-mono text-gray-500 shrink-0 min-w-[140px]">{key}</span>
            {isNested ? (
              <div className="ml-4 mt-0.5 pl-3 border-l-2 border-gray-100">
                <FieldValue value={val} />
              </div>
            ) : (
              <span className="text-sm break-all"><FieldValue value={val} /></span>
            )}
          </div>
        );
      })}
    </div>
  );
}

/* ------------------------------------------------------------------ */
/* Stage card                                                          */
/* ------------------------------------------------------------------ */

function StageCard({
  name,
  data,
  prevFieldKeys,
}: {
  name: StageName;
  data: Record<string, unknown>;
  prevFieldKeys: Set<string>;
}) {
  const meta = STAGE_META[name];

  // Collect top-level field keys for "new in this stage" highlighting
  const topKeys = Object.keys(data);
  const newKeys = topKeys.filter((k) => !prevFieldKeys.has(k));

  return (
    <div id={`stage-${name}`} className="rounded-2xl border border-gray-200 bg-white overflow-hidden">
      {/* Header */}
      <div className={`px-5 py-3 border-b border-gray-100 ${meta.color}`}>
        <div className="flex items-center justify-between">
          <div>
            <h3 className="text-sm font-semibold">{meta.label}</h3>
            <p className="text-[11px] opacity-70">{meta.description}</p>
          </div>
          <div className="text-right">
            <span className="text-[11px] font-mono">{topKeys.length} fields</span>
            {newKeys.length > 0 && (
              <span className="ml-2 text-[10px] bg-white/60 px-1.5 py-0.5 rounded font-medium">
                +{newKeys.length} new
              </span>
            )}
          </div>
        </div>
      </div>

      {/* Body */}
      <div className="px-5 py-3">
        <div className="space-y-0">
          {topKeys.map((key) => {
            const val = data[key];
            const isNew = newKeys.includes(key);
            const isNested =
              (typeof val === "object" && val !== null && !Array.isArray(val)) ||
              (Array.isArray(val) && val.length > 0 && typeof val[0] === "object");

            return (
              <div
                key={key}
                className={`${isNested ? "py-2" : "flex gap-3 py-1.5 items-baseline"} ${
                  isNew ? "bg-yellow-50/50 -mx-2 px-2 rounded" : ""
                }`}
              >
                <span
                  className={`text-[11px] font-mono shrink-0 min-w-[160px] ${
                    isNew ? "text-amber-600 font-semibold" : "text-gray-500"
                  }`}
                >
                  {key}
                  {isNew && <span className="ml-1 text-[9px] text-amber-500">NEW</span>}
                </span>
                {isNested ? (
                  <div className="ml-4 mt-0.5 pl-3 border-l-2 border-gray-100">
                    <FieldValue value={val} />
                  </div>
                ) : (
                  <span className="text-sm break-all">
                    <FieldValue value={val} />
                  </span>
                )}
              </div>
            );
          })}
        </div>
      </div>
    </div>
  );
}

/* ------------------------------------------------------------------ */
/* Geocoded stage (special — keyed by canonical address)               */
/* ------------------------------------------------------------------ */

function GeocodedCard({ data }: { data: Record<string, Record<string, unknown>> }) {
  const meta = STAGE_META.geocoded;
  const canonicals = Object.keys(data);

  return (
    <div id="stage-geocoded" className="rounded-2xl border border-gray-200 bg-white overflow-hidden">
      <div className={`px-5 py-3 border-b border-gray-100 ${meta.color}`}>
        <div className="flex items-center justify-between">
          <div>
            <h3 className="text-sm font-semibold">{meta.label}</h3>
            <p className="text-[11px] opacity-70">{meta.description}</p>
          </div>
          <span className="text-[11px] font-mono">{canonicals.length} address(es)</span>
        </div>
      </div>
      <div className="px-5 py-3 space-y-3">
        {canonicals.map((canon) => (
          <div key={canon}>
            <div className="text-xs font-mono text-gray-600 mb-1 break-all">{canon}</div>
            <div className="ml-4 pl-3 border-l-2 border-green-100">
              <FieldTable data={data[canon]} />
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}

/* ------------------------------------------------------------------ */
/* Main trace view                                                     */
/* ------------------------------------------------------------------ */

function TraceView({ data }: { data: TraceResult }) {
  const stages = data.stages;

  // Build cumulative field key sets for "new field" highlighting
  const fieldKeysByStage: Map<StageName, Set<string>> = new Map();
  const cumulativeKeys = new Set<string>();
  for (const name of STAGE_ORDER) {
    const stageData = stages[name];
    fieldKeysByStage.set(name, new Set(cumulativeKeys));
    if (stageData && typeof stageData === "object") {
      for (const k of Object.keys(stageData)) {
        cumulativeKeys.add(k);
      }
    }
  }

  return (
    <div className="space-y-4">
      {/* Header */}
      <div className="flex items-center gap-3 flex-wrap">
        <h2 className="text-lg font-semibold text-gray-900 font-mono">{data.id}</h2>
        <span className={`text-[11px] uppercase font-medium px-2 py-1 rounded-lg ${
          data.source === "realtrack" ? "bg-amber-100 text-amber-700" :
          data.source === "geowarehouse" ? "bg-teal-100 text-teal-700" :
          "bg-violet-100 text-violet-700"
        }`}>
          {data.source}
        </span>
        <span className="text-xs text-gray-400">
          {Object.keys(stages).length} of {STAGE_ORDER.length} stages
        </span>
      </div>

      {/* Timeline */}
      <StageTimeline stages={stages} />

      {/* Stage cards */}
      <div className="space-y-4">
        {STAGE_ORDER.map((name) => {
          const stageData = stages[name];
          if (!stageData) return null;

          // Geocoded stage has special structure
          if (name === "geocoded") {
            return <GeocodedCard key={name} data={stageData as Record<string, Record<string, unknown>>} />;
          }

          return (
            <StageCard
              key={name}
              name={name}
              data={stageData as Record<string, unknown>}
              prevFieldKeys={fieldKeysByStage.get(name) ?? new Set()}
            />
          );
        })}
      </div>
    </div>
  );
}

/* ------------------------------------------------------------------ */
/* Page                                                                */
/* ------------------------------------------------------------------ */

export default function TracePage() {
  const [searchParams, setSearchParams] = useSearchParams();
  const initialId = searchParams.get("id") ?? "";
  const { data, loading, error, trace } = useTrace();

  // Auto-trace if URL has ?id=
  useEffect(() => {
    if (initialId && !data && !loading) {
      trace(initialId);
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [initialId]);

  function handleSelect(id: string) {
    setSearchParams({ id });
    trace(id);
  }

  return (
    <div className="p-6 max-w-4xl mx-auto space-y-6">
      <div>
        <h1 className="text-xl font-bold text-gray-900 mb-1">Pipeline Trace</h1>
        <p className="text-sm text-gray-500">
          Follow a single record through every stage. See every field, what changed, what was added.
        </p>
      </div>

      <SearchBar onSelect={handleSelect} initialValue={initialId} />

      {loading && (
        <div className="text-sm text-gray-400 py-8 text-center">Loading trace...</div>
      )}

      {error && (
        <div className="text-sm text-red-600 bg-red-50 rounded-xl px-4 py-3">{error}</div>
      )}

      {data && <TraceView data={data} />}

      {!data && !loading && !error && (
        <div className="text-center py-16 text-gray-400">
          <p className="text-lg mb-2">Enter an ID to trace</p>
          <p className="text-sm">
            RT ID (e.g. RT196880), GW ID (e.g. GW00001), or Brand ID (e.g. BR_00045)
          </p>
        </div>
      )}
    </div>
  );
}
