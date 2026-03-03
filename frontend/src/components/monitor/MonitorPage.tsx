import { useMonitor } from "@/api/monitor";
import type { Gate, MonitorData } from "@/api/monitor";

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

function fmt(n: number | undefined): string {
  if (n === undefined || n === null) return "0";
  return n.toLocaleString();
}

function CoverageBar({ pct, label }: { pct: number; label: string }) {
  const color =
    pct >= 95 ? "bg-green-500" : pct >= 80 ? "bg-yellow-500" : "bg-red-500";
  return (
    <div className="flex items-center gap-2 text-xs">
      <span className="w-40 truncate text-[var(--slate-11)]">{label}</span>
      <div className="flex-1 h-2 bg-[var(--slate-4)] rounded-full overflow-hidden">
        <div className={`h-full ${color} rounded-full`} style={{ width: `${Math.min(pct, 100)}%` }} />
      </div>
      <span className="w-12 text-right tabular-nums font-medium">{pct.toFixed(1)}%</span>
    </div>
  );
}

function CoverageGroup({ title, data }: { title: string; data: Record<string, { count: number; pct: number }> }) {
  if (!data || Object.keys(data).length === 0) return null;
  return (
    <div className="mt-2">
      <div className="text-[10px] font-semibold uppercase tracking-widest text-[var(--slate-9)] mb-1">{title}</div>
      <div className="space-y-1">
        {Object.entries(data).map(([field, info]) => (
          <CoverageBar key={field} label={field} pct={info.pct} />
        ))}
      </div>
    </div>
  );
}

function SectionCard({ title, children, elapsed }: { title: string; children: React.ReactNode; elapsed?: number }) {
  return (
    <div className="bg-white/70 rounded-xl shadow-[0_1px_3px_rgba(0,0,0,0.04)] p-5">
      <div className="flex items-center justify-between mb-3">
        <h3 className="text-sm font-semibold uppercase tracking-wide text-[var(--slate-12)]">{title}</h3>
        {elapsed !== undefined && (
          <span className="text-[10px] text-[var(--slate-9)]">{elapsed.toFixed(1)}s</span>
        )}
      </div>
      {children}
    </div>
  );
}

function Stat({ label, value }: { label: string; value: string | number }) {
  return (
    <div>
      <div className="text-[10px] font-semibold uppercase tracking-widest text-[var(--slate-9)]">{label}</div>
      <div className="text-lg font-bold tabular-nums">{typeof value === "number" ? fmt(value) : value}</div>
    </div>
  );
}

function KeyVal({ label, value }: { label: string; value: string | number }) {
  return (
    <div className="flex justify-between text-xs py-0.5">
      <span className="text-[var(--slate-11)]">{label}</span>
      <span className="font-medium tabular-nums">{typeof value === "number" ? fmt(value) : value}</span>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Gate badges
// ---------------------------------------------------------------------------

function GateBadge({ gate }: { gate: Gate }) {
  const colors: Record<string, string> = {
    critical: "bg-red-100 text-red-800 border-red-200",
    warning: "bg-yellow-100 text-yellow-800 border-yellow-200",
    info: "bg-blue-100 text-blue-800 border-blue-200",
  };
  const cls = colors[gate.level] || colors.info;
  return (
    <div className={`rounded-lg border px-3 py-2 ${cls}`}>
      <div className="flex items-center gap-2 text-xs font-semibold">
        <span>{gate.id}</span>
        <span className="uppercase text-[10px]">{gate.level}</span>
        <span className="text-[var(--slate-11)]">({gate.stage})</span>
      </div>
      <div className="text-xs mt-0.5">{gate.message}</div>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Stage sections
// ---------------------------------------------------------------------------

function IngestSection({ m }: { m: Record<string, unknown> }) {
  const byType = (m.by_type || {}) as Record<string, number>;
  return (
    <SectionCard title="Ingestion" elapsed={m.elapsed as number}>
      <div className="grid grid-cols-3 gap-4 mb-3">
        <Stat label="HTML Files" value={m.total_html_files as number} />
        <Stat label="Tracker" value={m.tracker_total as number} />
        <Stat label="HTML Index" value={m.index_total as number} />
      </div>
      {(m.latest_batch_date as string) ? (
        <div className="text-xs text-[var(--slate-11)] mb-2">
          Latest batch: {m.latest_batch_date as string} ({fmt(m.latest_batch_count as number)} records)
        </div>
      ) : null}
      {Object.keys(byType).length > 0 && (
        <div className="space-y-0.5">
          {Object.entries(byType)
            .sort(([, a], [, b]) => b - a)
            .map(([t, c]) => (
              <KeyVal key={t} label={t} value={c} />
            ))}
        </div>
      )}
    </SectionCard>
  );
}

function ParsedSection({ m }: { m: Record<string, unknown> }) {
  const fc = (m.field_coverage || {}) as Record<string, { count: number; pct: number }>;
  const reviews = (m.reviews || {}) as Record<string, number>;
  return (
    <SectionCard title={`Parsed (${m.version || "?"})`} elapsed={m.elapsed as number}>
      <div className="grid grid-cols-2 gap-4 mb-3">
        <Stat label="Records" value={m.total_records as number} />
        <Stat label="Reviewed" value={(reviews.clean || 0) + (reviews.parser_issue || 0) + (reviews.bad_source || 0)} />
      </div>
      <CoverageGroup title="Field Coverage" data={fc} />
    </SectionCard>
  );
}

function NormalizedSection({ m }: { m: Record<string, unknown> }) {
  const bySource = (m.by_source || {}) as Record<string, number>;
  const cats = (m.categories || {}) as Record<string, number>;
  const cityStatuses = (m.city_statuses || {}) as Record<string, number>;
  const pfc = (m.property_field_coverage || {}) as Record<string, { count: number; pct: number }>;
  const sellerCov = (m.seller_field_coverage || {}) as Record<string, { count: number; pct: number }>;
  const buyerCov = (m.buyer_field_coverage || {}) as Record<string, { count: number; pct: number }>;
  const ownerCov = (m.owner_address_field_coverage || {}) as Record<string, { count: number; pct: number }>;
  const gwMeta = (m.gw_metadata || {}) as Record<string, { count: number; pct: number }>;
  const brandMeta = (m.brand_metadata || {}) as Record<string, { count: number; pct: number }>;
  const total = (m.total_records as number) || 0;
  return (
    <SectionCard title={`Normalized (${m.version || "?"})`} elapsed={m.elapsed as number}>
      <Stat label="Records" value={total} />
      {Object.keys(bySource).length > 0 && (
        <div className="mt-2">
          <div className="text-[10px] font-semibold uppercase tracking-widest text-[var(--slate-9)] mb-1">By Source</div>
          {Object.entries(bySource)
            .sort(([, a], [, b]) => b - a)
            .map(([s, c]) => (
              <KeyVal key={s} label={s} value={c} />
            ))}
        </div>
      )}
      {Object.keys(cats).length > 0 && (
        <div className="mt-2">
          <div className="text-[10px] font-semibold uppercase tracking-widest text-[var(--slate-9)] mb-1">Categories</div>
          {Object.entries(cats)
            .sort(([, a], [, b]) => b - a)
            .map(([cat, c]) => (
              <KeyVal key={cat} label={cat} value={c} />
            ))}
        </div>
      )}
      {Object.keys(cityStatuses).length > 0 && (
        <div className="mt-2">
          <div className="text-[10px] font-semibold uppercase tracking-widest text-[var(--slate-9)] mb-1">City Status</div>
          {Object.entries(cityStatuses)
            .sort(([, a], [, b]) => b - a)
            .map(([st, c]) => (
              <KeyVal key={st} label={st} value={`${fmt(c)} (${total ? ((c / total) * 100).toFixed(1) : 0}%)`} />
            ))}
        </div>
      )}
      <CoverageGroup title="Property Fields" data={pfc} />
      <CoverageGroup title="Seller Fields" data={sellerCov} />
      <CoverageGroup title="Buyer Fields" data={buyerCov} />
      <CoverageGroup title="Owner Address Fields" data={ownerCov} />
      <CoverageGroup title="GW Metadata" data={gwMeta} />
      <CoverageGroup title="Brand Metadata" data={brandMeta} />
    </SectionCard>
  );
}

function ExpandedSection({ m }: { m: Record<string, unknown> }) {
  const roles = (m.roles_present || {}) as Record<string, number>;
  const afc = (m.address_field_coverage || {}) as Record<string, { count: number; pct: number }>;
  return (
    <SectionCard title={`Expanded (${m.version || "?"})`} elapsed={m.elapsed as number}>
      <div className="grid grid-cols-3 gap-4 mb-2">
        <Stat label="Records" value={m.total_records as number} />
        <Stat label="Addresses" value={m.total_addresses as number} />
        <Stat label="Geocodable" value={m.geocodable as number} />
      </div>
      <KeyVal label="Skip geocode" value={m.skip_geocode as number} />
      <KeyVal label="Compound splits" value={m.compound_splits as number} />
      <KeyVal label="Has raw_coords" value={m.has_raw_coords as number} />
      {Object.keys(roles).length > 0 && (
        <div className="mt-2">
          <div className="text-[10px] font-semibold uppercase tracking-widest text-[var(--slate-9)] mb-1">Roles</div>
          {Object.entries(roles).map(([r, c]) => (
            <KeyVal key={r} label={r} value={c} />
          ))}
        </div>
      )}
      <CoverageGroup title="Address Field Coverage" data={afc} />
    </SectionCard>
  );
}

function GeocodedSection({ m }: { m: Record<string, unknown> }) {
  const byProvider = (m.by_provider || {}) as Record<string, number>;
  const accuracy = (m.accuracy || {}) as Record<string, number>;
  const confidence = (m.confidence || {}) as Record<string, number>;
  const matchDetail = (m.match_code_detail || {}) as Record<string, Record<string, number>>;
  return (
    <SectionCard title="Geocoded" elapsed={m.elapsed as number}>
      <div className="grid grid-cols-3 gap-4 mb-2">
        <Stat label="Addresses" value={m.total_addresses as number} />
        <Stat label="With Coords" value={m.with_coords as number} />
        <Stat label="Missing" value={m.missing_coords as number} />
      </div>
      <CoverageBar label="Coverage" pct={(m.coverage_pct as number) || 0} />
      <KeyVal label="Multi-provider" value={m.multi_provider as number} />
      {Object.keys(byProvider).length > 0 && (
        <div className="mt-2">
          <div className="text-[10px] font-semibold uppercase tracking-widest text-[var(--slate-9)] mb-1">By Provider</div>
          {Object.entries(byProvider)
            .sort(([, a], [, b]) => b - a)
            .map(([p, c]) => (
              <KeyVal key={p} label={p} value={c} />
            ))}
        </div>
      )}
      {Object.keys(accuracy).length > 0 && (
        <div className="mt-2">
          <div className="text-[10px] font-semibold uppercase tracking-widest text-[var(--slate-9)] mb-1">Accuracy</div>
          {Object.entries(accuracy)
            .sort(([, a], [, b]) => b - a)
            .map(([a, c]) => (
              <KeyVal key={a} label={a} value={c} />
            ))}
        </div>
      )}
      {Object.keys(confidence).length > 0 && (
        <div className="mt-2">
          <div className="text-[10px] font-semibold uppercase tracking-widest text-[var(--slate-9)] mb-1">Confidence</div>
          {Object.entries(confidence)
            .sort(([, a], [, b]) => b - a)
            .map(([c, cnt]) => (
              <KeyVal key={c} label={c} value={cnt} />
            ))}
        </div>
      )}
      {Object.keys(matchDetail).length > 0 && (
        <div className="mt-2">
          <div className="text-[10px] font-semibold uppercase tracking-widest text-[var(--slate-9)] mb-1">Match Code Detail</div>
          {Object.entries(matchDetail).map(([field, dist]) => {
            const top = Object.entries(dist).sort(([, a], [, b]) => b - a).slice(0, 3);
            return (
              <div key={field} className="flex justify-between text-xs py-0.5">
                <span className="text-[var(--slate-11)]">{field}</span>
                <span className="font-medium tabular-nums text-right">{top.map(([k, v]) => `${k}=${fmt(v)}`).join(", ")}</span>
              </div>
            );
          })}
        </div>
      )}
    </SectionCard>
  );
}

function ParcelsSection({ m }: { m: Record<string, unknown> }) {
  const mfc = (m.municipal_field_coverage || {}) as Record<string, { count: number; pct: number }>;
  return (
    <SectionCard title="Parcels" elapsed={m.elapsed as number}>
      <div className="grid grid-cols-2 gap-4 mb-2">
        <Stat label="Provincial" value={m.provincial_total as number} />
        <Stat label="Municipal" value={m.municipal_total as number} />
      </div>
      <KeyVal label="Unique ARNs" value={m.unique_arns as number} />
      <KeyVal label="Queried points" value={m.queried_points as number} />
      <KeyVal label="Provincial links" value={m.provincial_property_links as number} />
      <KeyVal label="Provincial no cov" value={m.provincial_no_coverage as number} />
      <KeyVal label="Municipal links" value={m.municipal_property_links as number} />
      <KeyVal label="Services registry" value={m.services_total as number} />
      <KeyVal label="Prop-parcel index" value={m.property_parcel_index_total as number} />
      <KeyVal label="Parcel cache" value={m.parcel_cache_total as number} />
      {m.provincial_raw_size_mb !== undefined && <KeyVal label="Provincial file" value={`${m.provincial_raw_size_mb} MB`} />}
      {m.municipal_parcels_size_mb !== undefined && <KeyVal label="Municipal file" value={`${m.municipal_parcels_size_mb} MB`} />}
      <CoverageGroup title="Municipal Field Coverage" data={mfc} />
    </SectionCard>
  );
}

function PropertiesSection({ m }: { m: Record<string, unknown> }) {
  const fc = (m.field_coverage || {}) as Record<string, { count: number; pct: number }>;
  const gwc = (m.gw_data_coverage || {}) as Record<string, { count: number; pct: number }>;
  return (
    <SectionCard title="Properties" elapsed={m.elapsed as number}>
      <div className="grid grid-cols-2 gap-4 mb-2">
        <Stat label="Total" value={m.total as number} />
        <Stat label="With Coords" value={`${fmt(m.with_coords as number)} (${((m.with_coords_pct as number) || 0).toFixed(1)}%)`} />
      </div>
      <KeyVal label="Multi-transaction" value={m.multi_transaction as number} />
      <KeyVal label="Brand matched" value={m.brand_matched as number} />
      <CoverageGroup title="Field Coverage" data={fc} />
      <CoverageGroup title="GW Data Sub-fields" data={gwc} />
    </SectionCard>
  );
}

function GeoWarehouseSection({ m }: { m: Record<string, unknown> }) {
  const sc = (m.summary_coverage || {}) as Record<string, { count: number; pct: number }>;
  const rc = (m.registry_coverage || {}) as Record<string, { count: number; pct: number }>;
  const ssc = (m.site_structure_coverage || {}) as Record<string, { count: number; pct: number }>;
  return (
    <SectionCard title="GeoWarehouse" elapsed={m.elapsed as number}>
      <div className="grid grid-cols-3 gap-4 mb-2">
        <Stat label="HTML Files" value={m.html_files as number} />
        <Stat label="Parsed" value={m.parsed_records as number} />
        <Stat label="Unique PINs" value={m.unique_pins as number} />
      </div>
      <KeyVal label="Has GW ID" value={m.has_gw_id as number} />
      <KeyVal label="Sales history" value={`${fmt(m.with_sales_history as number)} records, ${fmt(m.total_sales_entries as number)} entries`} />
      <CoverageGroup title="Summary Block" data={sc} />
      <CoverageGroup title="Registry Block" data={rc} />
      <CoverageGroup title="Site Structure" data={ssc} />
    </SectionCard>
  );
}

function BrandsSection({ m }: { m: Record<string, unknown> }) {
  const fc = (m.field_coverage || {}) as Record<string, { count: number; pct: number }>;
  return (
    <SectionCard title="Brands" elapsed={m.elapsed as number}>
      <div className="grid grid-cols-2 gap-4 mb-2">
        <Stat label="Brands" value={m.total_brands as number} />
        <Stat label="Stores" value={m.total_stores as number} />
      </div>
      <CoverageGroup title="Field Coverage" data={fc} />
    </SectionCard>
  );
}

// ---------------------------------------------------------------------------
// Legacy / frozen
// ---------------------------------------------------------------------------

function LegacySection({ legacy }: { legacy: { parties: Record<string, unknown> } }) {
  const parties = legacy.parties;
  if (!parties || !(parties.total as number)) return null;

  return (
    <div>
      <h2 className="text-sm font-semibold uppercase tracking-wide text-[var(--slate-9)] mb-3">
        Legacy / Frozen
      </h2>
      <div className="grid grid-cols-1 lg:grid-cols-2 xl:grid-cols-3 gap-4">
        <div className="bg-white/40 rounded-xl border border-dashed border-[var(--slate-6)] p-5 opacity-70">
          <div className="flex items-center justify-between mb-3">
            <h3 className="text-sm font-semibold uppercase tracking-wide text-[var(--slate-9)]">Parties (frozen)</h3>
            <span className="text-[10px] px-2 py-0.5 rounded-full bg-[var(--slate-3)] text-[var(--slate-9)] font-semibold">LEGACY</span>
          </div>
          <p className="text-xs text-[var(--slate-9)] mb-3">
            Will be rebuilt as a read-only view on clean compiled data.
          </p>
          <KeyVal label="Groups" value={parties.total as number} />
          <KeyVal label="Companies" value={parties.companies as number} />
          <KeyVal label="Persons" value={parties.persons as number} />
          <KeyVal label="Appearances" value={parties.total_appearances as number} />
          <KeyVal label="RT IDs linked" value={parties.total_rt_ids_linked as number} />
        </div>
      </div>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Data flow arrow
// ---------------------------------------------------------------------------

function FlowSummary({ data }: { data: MonitorData }) {
  const steps = [
    { label: "HTML Files", value: fmt((data.ingest?.total_html_files as number) || 0) },
    { label: "Parsed", value: fmt((data.parsed?.total_records as number) || 0) },
    { label: "Normalized", value: fmt((data.normalized?.total_records as number) || 0) },
    { label: "Expanded Addrs", value: fmt((data.expanded?.total_addresses as number) || 0) },
    { label: "Geocoded", value: `${fmt((data.geocoded?.with_coords as number) || 0)} / ${fmt((data.geocoded?.total_addresses as number) || 0)}` },
    { label: "Parcels", value: fmt((data.parcels?.provincial_total as number) || 0) },
    { label: "Properties", value: fmt((data.properties?.total as number) || 0) },
  ];

  return (
    <div className="bg-white/70 rounded-xl shadow-[0_1px_3px_rgba(0,0,0,0.04)] p-5 mb-6">
      <h3 className="text-sm font-semibold uppercase tracking-wide text-[var(--slate-12)] mb-3">Data Flow</h3>
      <div className="flex items-center gap-1 flex-wrap">
        {steps.map((s, i) => (
          <div key={s.label} className="flex items-center gap-1">
            <div className="text-center px-3 py-2 bg-[var(--slate-2)] rounded-lg min-w-[90px]">
              <div className="text-[10px] font-semibold uppercase tracking-widest text-[var(--slate-9)]">{s.label}</div>
              <div className="text-sm font-bold tabular-nums">{s.value}</div>
            </div>
            {i < steps.length - 1 && <span className="text-[var(--slate-8)] text-lg">&rarr;</span>}
          </div>
        ))}
      </div>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Main page
// ---------------------------------------------------------------------------

export default function MonitorPage() {
  const { data, loading, error, refresh } = useMonitor();

  if (loading) {
    return (
      <div className="flex-1 flex items-center justify-center">
        <p className="text-sm text-[var(--slate-9)]">Collecting metrics across all stages...</p>
      </div>
    );
  }

  if (error || !data) {
    return (
      <div className="flex-1 flex items-center justify-center">
        <div className="text-center">
          <p className="text-sm text-red-600 mb-2">Failed to load metrics</p>
          <p className="text-xs text-[var(--slate-9)]">{error}</p>
        </div>
      </div>
    );
  }

  const gates = data.gates || [];
  const criticalCount = gates.filter((g) => g.level === "critical").length;
  const warningCount = gates.filter((g) => g.level === "warning").length;

  return (
    <div className="flex-1 overflow-auto p-6 space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold">Pipeline Monitor</h1>
          <p className="text-xs text-[var(--slate-9)] mt-1">
            Collected at {data.collected_at}
            {criticalCount > 0 && (
              <span className="ml-2 px-2 py-0.5 rounded-full bg-red-100 text-red-800 text-[10px] font-semibold">
                {criticalCount} CRITICAL
              </span>
            )}
            {warningCount > 0 && (
              <span className="ml-2 px-2 py-0.5 rounded-full bg-yellow-100 text-yellow-800 text-[10px] font-semibold">
                {warningCount} WARNING
              </span>
            )}
          </p>
        </div>
        <button
          onClick={refresh}
          className="px-4 py-2 text-sm bg-[var(--slate-12)] text-[var(--slate-1)] rounded-lg hover:opacity-90 transition-opacity"
        >
          Refresh
        </button>
      </div>

      {/* Data flow summary */}
      <FlowSummary data={data} />

      {/* Quality gates */}
      {gates.length > 0 && (
        <div>
          <h2 className="text-sm font-semibold uppercase tracking-wide text-[var(--slate-12)] mb-2">
            Quality Gates ({gates.length} triggered)
          </h2>
          <div className="space-y-2">
            {gates.map((g) => (
              <GateBadge key={g.id} gate={g} />
            ))}
          </div>
        </div>
      )}

      {/* Stage cards — main pipeline */}
      <div>
        <h2 className="text-sm font-semibold uppercase tracking-wide text-[var(--slate-12)] mb-3">Pipeline Stages</h2>
        <div className="grid grid-cols-1 lg:grid-cols-2 xl:grid-cols-3 gap-4">
          <IngestSection m={data.ingest} />
          <ParsedSection m={data.parsed} />
          <NormalizedSection m={data.normalized} />
          <ExpandedSection m={data.expanded} />
          <GeocodedSection m={data.geocoded} />
          <ParcelsSection m={data.parcels} />
          <PropertiesSection m={data.properties} />
        </div>
      </div>

      {/* Supporting data sources */}
      <div>
        <h2 className="text-sm font-semibold uppercase tracking-wide text-[var(--slate-12)] mb-3">Data Sources</h2>
        <div className="grid grid-cols-1 lg:grid-cols-2 xl:grid-cols-3 gap-4">
          <GeoWarehouseSection m={data.geowarehouse} />
          <BrandsSection m={data.brands} />
        </div>
      </div>

      {/* Legacy / frozen */}
      {data.legacy && (
        <LegacySection legacy={data.legacy} />
      )}
    </div>
  );
}
