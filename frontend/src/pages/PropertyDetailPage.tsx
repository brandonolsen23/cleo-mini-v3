import { useState, useEffect, useMemo, useCallback } from "react";
import { useParams, useNavigate } from "react-router-dom";
import { Text, Badge, Heading, Separator, Spinner } from "@radix-ui/themes";
import {
  ArrowLeft,
  CaretLeft,
  CaretRight,
  Copy,
  Check,
  MapPin,
  Buildings,
  User,
  Receipt,
} from "@phosphor-icons/react";
import Map, { Source, Layer } from "react-map-gl/mapbox";
import { formatCurrency, formatDate, formatStreet } from "@/lib/utils";
import { categoryColor } from "@/lib/theme";
import { fetchApi } from "@/api/client";
import { FlagIssueMenu } from "@/components/ui/FlagIssueMenu";
import type { PropertyDetail } from "@/types";

const MAPBOX_TOKEN = import.meta.env.VITE_MAPBOX_TOKEN;
const JADE_9 = "#26997b";
const JADE_11 = "#208368";

const SOURCE_LABELS: Record<string, string> = {
  realtrack: "RT",
  geowarehouse: "GW",
  brand: "BR",
  osm: "OSM",
};

const METHOD_LABELS: Record<string, string> = {
  arn: "ARN Direct",
  pin: "PIN Bridge",
  spatial: "Spatial",
  none: "Unresolved",
};

export function PropertyDetailPage() {
  const { id } = useParams<{ id: string }>();
  const navigate = useNavigate();
  const [prop, setProp] = useState<PropertyDetail | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  useEffect(() => {
    if (!id) return;
    setLoading(true);
    fetchApi<PropertyDetail>(`/properties/${id}`)
      .then(setProp)
      .catch((e) => setError(e.message))
      .finally(() => setLoading(false));
  }, [id]);

  if (loading) {
    return (
      <div className="flex items-center justify-center py-20">
        <Spinner size="3" />
      </div>
    );
  }

  if (error || !prop) {
    return (
      <div className="flex flex-col items-center justify-center py-20">
        <Text size="3" color="gray">
          {error || "Property not found"}
        </Text>
        <button
          onClick={() => navigate(-1)}
          className="mt-4 text-[13px] font-medium text-[var(--accent-11)] hover:underline"
        >
          Back to Properties
        </button>
      </div>
    );
  }

  return (
    <div className="flex flex-col gap-6">
      {/* Back link */}
      <button
        onClick={() => navigate(-1)}
        className="inline-flex items-center gap-1.5 self-start rounded-[var(--radius-2)] px-2.5 py-1.5 text-[13px] font-medium text-[var(--accent-11)] hover:bg-[var(--accent-a3)]"
      >
        <ArrowLeft size={14} />
        Properties
      </button>

      {/* Header */}
      <div className="flex items-start justify-between">
        <div>
          <Heading size="6" weight="medium">
            {formatStreet(prop.primary_address)}
          </Heading>
          <Text as="p" size="2" color="gray" className="mt-1">
            {prop.city}
          </Text>
        </div>
        <div className="flex items-center gap-2">
          {prop.sources.map((s) => (
            <Badge key={s} size="2" variant="soft" color="gray">
              {SOURCE_LABELS[s] ?? s}
            </Badge>
          ))}
          <FlagIssueMenu
            sourceId={prop.property_id}
            fields={["primary_address", "city", "geocode_location", "parcel_assignment", "missing_data", "duplicate_property"]}
            page="property_detail"
            context={prop.primary_address}
          />
        </div>
      </div>

      {/* Tenant badges */}
      {prop.tenants.length > 0 && (
        <div className="flex flex-wrap gap-1.5">
          {prop.tenants.map((t) => (
            <Badge
              key={t.source_id}
              size="1"
              variant="soft"
              color={categoryColor(t.category || "")}
            >
              {t.brand || t.name || t.source_id}
            </Badge>
          ))}
        </div>
      )}

      <Separator size="4" />

      {/* Two-column layout */}
      <div className="grid grid-cols-1 gap-6 lg:grid-cols-3">
        {/* Left column: 2/3 width */}
        <div className="flex flex-col gap-6 lg:col-span-2">
          {/* Current Owner */}
          {prop.current_owner && (
            <Card
              title="Current Owner"
              icon={<User size={16} />}
              action={
                <FlagIssueMenu
                  sourceId={prop.current_owner.from_transaction}
                  fields={["company_name", "contact_name", "phone", "corp_address"]}
                  page="property_detail"
                  context={prop.current_owner.name}
                />
              }
            >
              <DetailRow label="Name" value={prop.current_owner.name} />
              {prop.current_owner.contact && (
                <DetailRow
                  label="Contact"
                  value={prop.current_owner.contact}
                />
              )}
              {prop.current_owner.attention &&
                prop.current_owner.attention !== prop.current_owner.contact && (
                <DetailRow
                  label="Attention"
                  value={prop.current_owner.attention}
                />
              )}
              {(prop.current_owner.phones?.length ?? 0) > 0 && (
                <DetailRow
                  label="Phone"
                  value={prop.current_owner.phones.join(", ")}
                  copyable
                />
              )}
              {(prop.current_owner.aliases?.length ?? 0) > 0 && (
                <DetailRow
                  label="Aliases"
                  value={prop.current_owner.aliases.join(", ")}
                />
              )}
              {(prop.current_owner.company_lines?.length ?? 0) > 0 && (
                <DetailRow
                  label="Company"
                  value={prop.current_owner.company_lines.join(", ")}
                />
              )}
              <DetailRow
                label="Source"
                value={prop.current_owner.from_transaction}
              />
            </Card>
          )}

          {/* Transaction History */}
          {prop.transactions.length > 0 && (
            <Card
              title={`Transaction History (${prop.transactions.length})`}
              icon={<Receipt size={16} />}
            >
              <div className="flex flex-col gap-4">
                {prop.transactions.map((txn) => (
                  <TransactionCard key={txn.rt_id} txn={txn} />
                ))}
              </div>
            </Card>
          )}

        </div>

        {/* Right column: 1/3 width */}
        <div className="flex flex-col gap-6">
          {/* Photos */}
          <PhotoCard prop={prop} />

          {/* Parcel mini-map */}
          <ParcelMapCard prop={prop} />

          {/* Parcel Info */}
          <Card
            title="Parcel"
            icon={<MapPin size={16} />}
            action={
              <FlagIssueMenu
                sourceId={prop.property_id}
                fields={["arn", "pin", "parcel_boundary", "centroid", "parcel_method"]}
                page="property_detail"
                context={prop.arn}
              />
            }
          >
            <DetailRow label="ARN" value={prop.arn} copyable />
            {prop.pins.length > 0 && (
              <DetailRow label="PIN" value={prop.pins.join(", ")} />
            )}
            <DetailRow
              label="Method"
              value={METHOD_LABELS[prop.parcel_method] ?? prop.parcel_method}
            />
            <DetailRow
              label="Confidence"
              value={prop.parcel_confidence}
            />
            {prop.centroid_lat && prop.centroid_lng && (
              <DetailRow
                label="Centroid"
                value={`${prop.centroid_lat.toFixed(5)}, ${prop.centroid_lng.toFixed(5)}`}
              />
            )}
          </Card>

          {/* Site Details */}
          {(prop.building_sf || prop.site_area || prop.zoning) && (
            <Card
              title="Site"
              icon={<Buildings size={16} />}
            >
              {prop.building_sf && (
                <DetailRow
                  label="Building SF"
                  value={prop.building_sf.toLocaleString()}
                />
              )}
              {prop.site_area && (
                <DetailRow
                  label="Site Area"
                  value={`${prop.site_area} ${prop.site_area_units}`}
                />
              )}
              {prop.zoning && (
                <DetailRow label="Zoning" value={prop.zoning} />
              )}
              {prop.legal_description && (
                <DetailRow
                  label="Legal"
                  value={prop.legal_description}
                />
              )}
            </Card>
          )}

          {/* All Addresses */}
          {prop.all_addresses.length > 1 && (
            <Card title="All Addresses">
              <div className="flex flex-col gap-1">
                {prop.all_addresses.map((addr, i) => (
                  <Text
                    key={i}
                    size="2"
                    className={
                      addr === prop.primary_address
                        ? "font-medium"
                        : "text-[var(--gray-11)]"
                    }
                  >
                    {addr}
                  </Text>
                ))}
              </div>
            </Card>
          )}

          {/* Source Records */}
          <Card title="Source Records">
            <Text size="1" weight="medium" className="mb-2 block text-[var(--gray-11)]">
              {prop.property_id}
            </Text>
            <div className="flex flex-wrap gap-1.5">
              {prop.source_records.map((sid) => (
                <Badge key={sid} size="1" variant="outline" color="gray">
                  {sid}
                </Badge>
              ))}
            </div>
          </Card>
        </div>
      </div>
    </div>
  );
}

/* ------------------------------------------------------------------ */
/* Card wrapper                                                        */
/* ------------------------------------------------------------------ */

function Card({
  title,
  icon,
  action,
  children,
}: {
  title: string;
  icon?: React.ReactNode;
  action?: React.ReactNode;
  children: React.ReactNode;
}) {
  return (
    <div className="rounded-[var(--card-radius)] border border-[var(--gray-6)] p-5">
      <div className="mb-3 flex items-center justify-between text-[var(--gray-11)]">
        <div className="flex items-center gap-2">
          {icon}
          <Text size="2" weight="medium" className="text-[var(--gray-12)]">
            {title}
          </Text>
        </div>
        {action}
      </div>
      {children}
    </div>
  );
}

/* ------------------------------------------------------------------ */
/* Detail row                                                          */
/* ------------------------------------------------------------------ */

function DetailRow({
  label,
  value,
  copyable,
}: {
  label: string;
  value: string;
  copyable?: boolean;
}) {
  const [copied, setCopied] = useState(false);

  if (!value) return null;

  const handleCopy = () => {
    navigator.clipboard.writeText(value);
    setCopied(true);
    setTimeout(() => setCopied(false), 1500);
  };

  return (
    <div className="flex items-start justify-between border-b border-[var(--gray-4)] py-1.5 last:border-b-0">
      <Text size="2" color="gray" className="shrink-0">
        {label}
      </Text>
      <div className="flex items-center gap-1.5 text-right">
        <Text size="2" className="max-w-[280px] break-words text-right">
          {value}
        </Text>
        {copyable && (
          <button
            onClick={handleCopy}
            className="shrink-0 text-[var(--gray-9)] hover:text-[var(--gray-11)]"
          >
            {copied ? <Check size={13} /> : <Copy size={13} />}
          </button>
        )}
      </div>
    </div>
  );
}

/* ------------------------------------------------------------------ */
/* Photo carousel card                                                 */
/* ------------------------------------------------------------------ */

function PhotoCard({ prop }: { prop: PropertyDetail }) {
  const photos = useMemo(() => {
    const all: string[] = [];
    for (const txn of prop.transactions) {
      for (const url of txn.photos ?? []) {
        if (!all.includes(url)) all.push(url);
      }
    }
    return all;
  }, [prop.transactions]);

  const [idx, setIdx] = useState(0);

  const prev = useCallback(
    () => setIdx((i) => (i - 1 + photos.length) % photos.length),
    [photos.length],
  );
  const next = useCallback(
    () => setIdx((i) => (i + 1) % photos.length),
    [photos.length],
  );

  if (photos.length === 0) return null;

  return (
    <div className="group relative overflow-hidden rounded-[var(--card-radius)] border border-[var(--gray-6)]">
      <div className="relative aspect-square bg-[var(--gray-3)]">
        <img
          src={photos[idx]}
          alt={`Property photo ${idx + 1}`}
          className="h-full w-full object-cover"
        />

        {/* Counter */}
        <div className="absolute left-3 top-3 rounded-[var(--radius-2)] bg-black/50 px-2 py-0.5">
          <Text size="1" className="text-white">
            {idx + 1} / {photos.length}
          </Text>
        </div>

        {/* Prev / Next arrows */}
        {photos.length > 1 && (
          <>
            <button
              onClick={prev}
              className="absolute bottom-3 right-12 flex h-7 w-7 items-center justify-center rounded-full bg-white/80 text-[var(--gray-11)] opacity-0 transition-opacity hover:bg-white group-hover:opacity-100"
            >
              <CaretLeft size={14} weight="bold" />
            </button>
            <button
              onClick={next}
              className="absolute bottom-3 right-3 flex h-7 w-7 items-center justify-center rounded-full bg-white/80 text-[var(--gray-11)] opacity-0 transition-opacity hover:bg-white group-hover:opacity-100"
            >
              <CaretRight size={14} weight="bold" />
            </button>
          </>
        )}
      </div>
    </div>
  );
}

/* ------------------------------------------------------------------ */
/* Parcel mini-map card                                                */
/* ------------------------------------------------------------------ */

function ParcelMapCard({ prop }: { prop: PropertyDetail }) {
  const [geojson, setGeojson] = useState<any>(null);

  // Fetch parcel geometry by ARN
  useEffect(() => {
    if (!prop.arn) return;
    fetchApi<any>(`/parcels/cache/arn/${prop.arn}`)
      .then(setGeojson)
      .catch(() => {}); // silently skip if no parcel
  }, [prop.arn]);

  // Compute bounds from polygon coordinates
  const bounds = useMemo(() => {
    if (!geojson?.geometry?.coordinates) return null;
    let minLng = Infinity, minLat = Infinity, maxLng = -Infinity, maxLat = -Infinity;
    const coords = geojson.geometry.type === "MultiPolygon"
      ? geojson.geometry.coordinates.flat(2)
      : geojson.geometry.coordinates.flat(1);
    for (const [lng, lat] of coords) {
      if (lng < minLng) minLng = lng;
      if (lng > maxLng) maxLng = lng;
      if (lat < minLat) minLat = lat;
      if (lat > maxLat) maxLat = lat;
    }
    // Add padding
    const padLng = (maxLng - minLng) * 0.3 || 0.001;
    const padLat = (maxLat - minLat) * 0.3 || 0.001;
    return {
      longitude: (minLng + maxLng) / 2,
      latitude: (minLat + maxLat) / 2,
      bounds: [
        [minLng - padLng, minLat - padLat],
        [maxLng + padLng, maxLat + padLat],
      ] as [[number, number], [number, number]],
    };
  }, [geojson]);

  if (!geojson || !bounds) return null;

  const fc = { type: "FeatureCollection" as const, features: [geojson] };

  return (
    <div className="overflow-hidden rounded-[var(--card-radius)] border border-[var(--gray-6)]">
      <div className="aspect-square">
        <Map
          initialViewState={{
            bounds: bounds.bounds,
            fitBoundsOptions: { padding: 20 },
          }}
          mapboxAccessToken={MAPBOX_TOKEN}
          mapStyle="mapbox://styles/mapbox/light-v11"
          interactive={true}
          attributionControl={false}
          style={{ width: "100%", height: "100%" }}
        >
          <Source id="parcel" type="geojson" data={fc}>
            <Layer
              id="parcel-fill"
              type="fill"
              paint={{
                "fill-color": JADE_9,
                "fill-opacity": 0.15,
              }}
            />
            <Layer
              id="parcel-outline"
              type="line"
              paint={{
                "line-color": JADE_11,
                "line-width": 2,
              }}
            />
          </Source>
        </Map>
      </div>
    </div>
  );
}

/* ------------------------------------------------------------------ */
/* Transaction card                                                    */
/* ------------------------------------------------------------------ */

function TransactionCard({
  txn,
}: {
  txn: PropertyDetail["transactions"][number];
}) {
  const [expanded, setExpanded] = useState(false);

  return (
    <div className="rounded-lg border border-[var(--gray-4)] p-4">
      {/* Summary row */}
      <div className="flex w-full items-center justify-between">
        <button
          onClick={() => setExpanded((v) => !v)}
          className="flex flex-1 items-center gap-3 text-left"
        >
          <Badge size="1" variant="soft" color="gray">
            {txn.rt_id}
          </Badge>
          <Text size="2">{txn.sale_date ? formatDate(txn.sale_date) : "No date"}</Text>
          <Text size="2" weight="medium">
            {txn.sale_price
              ? formatCurrency(txn.sale_price)
              : "No price"}
          </Text>
        </button>
        <div className="flex items-center gap-2 shrink-0">
          <button
            onClick={() => setExpanded((v) => !v)}
            className="text-left"
          >
            <Text size="1" color="gray">
              {expanded ? "Collapse" : "Details"}
            </Text>
          </button>
          <FlagIssueMenu
            sourceId={txn.rt_id}
            fields={[
              "seller_company_name", "seller_contact_name", "seller_phone", "seller_corp_address",
              "buyer_company_name", "buyer_contact_name", "buyer_phone", "buyer_corp_address",
              "sale_price", "sale_date",
            ]}
            page="property_detail"
            context={txn.seller_name || txn.buyer_name || ""}
          />
        </div>
      </div>

      {expanded && (
        <div className="mt-3 grid grid-cols-2 gap-4 border-t border-[var(--gray-4)] pt-3">
          {/* Seller */}
          <div>
            <Text
              size="1"
              weight="medium"
              color="gray"
              className="mb-1 block uppercase tracking-wider"
            >
              Seller
            </Text>
            <Text size="2" weight="medium" className="block">
              {txn.seller_name || "\u2014"}
            </Text>
            {txn.seller_contact && (
              <Text size="2" color="gray" className="block">
                {txn.seller_contact}
              </Text>
            )}
            {txn.seller_phones?.length > 0 && (
              <Text size="2" className="block text-[var(--accent-11)]">
                {txn.seller_phones.join(", ")}
              </Text>
            )}
          </div>

          {/* Buyer */}
          <div>
            <Text
              size="1"
              weight="medium"
              color="gray"
              className="mb-1 block uppercase tracking-wider"
            >
              Buyer
            </Text>
            <Text size="2" weight="medium" className="block">
              {txn.buyer_name || "\u2014"}
            </Text>
            {txn.buyer_contact && (
              <Text size="2" color="gray" className="block">
                {txn.buyer_contact}
              </Text>
            )}
            {txn.buyer_phones?.length > 0 && (
              <Text size="2" className="block text-[var(--accent-11)]">
                {txn.buyer_phones.join(", ")}
              </Text>
            )}
          </div>

          {/* Consideration */}
          {txn.consideration?.verbatim && (
            <div className="col-span-2">
              <Text
                size="1"
                weight="medium"
                color="gray"
                className="mb-1 block uppercase tracking-wider"
              >
                Consideration
              </Text>
              <Text size="2" className="block">
                {txn.consideration.verbatim}
              </Text>
            </div>
          )}

          {/* Site details */}
          <div className="col-span-2 flex flex-wrap gap-x-6 gap-y-1">
            {txn.building_sf && (
              <Text size="2" color="gray">
                Building: {txn.building_sf.toLocaleString()} SF
              </Text>
            )}
            {txn.site_area && (
              <Text size="2" color="gray">
                Site: {txn.site_area} {txn.site_area_units}
              </Text>
            )}
            {txn.zoning && (
              <Text size="2" color="gray">
                Zoning: {txn.zoning}
              </Text>
            )}
            {txn.broker_name && (
              <Text size="2" color="gray">
                Broker: {txn.broker_name}
              </Text>
            )}
          </div>

          {/* Description */}
          {txn.description && (
            <div className="col-span-2">
              <Text size="2" color="gray" className="block whitespace-pre-wrap">
                {txn.description}
              </Text>
            </div>
          )}
        </div>
      )}
    </div>
  );
}
