import { useState, useEffect } from "react";
import { useParams, useNavigate, Link } from "react-router-dom";
import { ArrowLeft, ArrowSquareOut, PencilSimple, FloppyDisk, X } from "@phosphor-icons/react";
import { useProperty, updateProperty } from "../../api/properties";
import DataIssueCard from "../shared/DataIssueCard";
import MapLink from "../shared/MapLink";
import PropertyOutreachCard from "../outreach/PropertyOutreachCard";
import PropertyDealCard from "../crm/PropertyDealCard";
import type { GWRecord } from "../../types/property";
import { Card, CardHeader, CardTitle, CardContent } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";

function Field({ label, value }: { label: string; value: string | undefined }) {
  if (!value) return null;
  return (
    <div className="py-1.5">
      <dt className="text-xs text-muted-foreground font-medium">{label}</dt>
      <dd className="text-sm mt-0.5">{value}</dd>
    </div>
  );
}

function StreetViewCard({ propId }: { propId: string }) {
  const [status, setStatus] = useState<"loading" | "loaded" | "none" | "error">("loading");
  const imgUrl = `/api/properties/${propId}/streetview`;

  return (
    <Card>
      <CardHeader className="border-b border-border">
        <CardTitle>Street View</CardTitle>
      </CardHeader>
      <CardContent>
        {status === "loading" && (
          <div className="aspect-video bg-muted flex items-center justify-center">
            <span className="text-sm text-muted-foreground">Loading Street View...</span>
          </div>
        )}
        {status === "none" && (
          <p className="text-sm text-muted-foreground py-6 text-center">
            No Street View coverage available
          </p>
        )}
        {status === "error" && (
          <p className="text-sm text-muted-foreground py-6 text-center">
            Street View unavailable
          </p>
        )}
        <div className={`aspect-video bg-muted overflow-hidden ${status !== "loaded" && status !== "loading" ? "hidden" : ""}`}>
          <img
            src={imgUrl}
            alt="Street View"
            className={`w-full h-full object-cover ${status === "loading" ? "opacity-0" : ""}`}
            onLoad={() => setStatus("loaded")}
            onError={(e) => {
              const img = e.target as HTMLImageElement;
              // Distinguish between no coverage (404) and other errors
              setStatus("none");
              img.style.display = "none";
            }}
          />
        </div>
      </CardContent>
    </Card>
  );
}

function FootprintCard({ propId }: { propId: string }) {
  const [data, setData] = useState<{
    footprint_id: string;
    method: string;
    area_sqm: number | null;
    building_type: string;
    building_name: string;
  } | null>(null);
  const [status, setStatus] = useState<"loading" | "loaded" | "none">("loading");

  useEffect(() => {
    fetch(`/api/properties/${propId}/footprint`)
      .then((r) => {
        if (!r.ok) throw new Error("not found");
        return r.json();
      })
      .then((d) => {
        setData(d);
        setStatus("loaded");
      })
      .catch(() => setStatus("none"));
  }, [propId]);

  if (status === "none") return null;
  if (status === "loading") return null;
  if (!data) return null;

  return (
    <Card>
      <CardHeader className="border-b border-border">
        <CardTitle>Building Footprint</CardTitle>
      </CardHeader>
      <CardContent>
        <dl className="grid grid-cols-2 gap-x-6">
          <div className="py-1.5">
            <dt className="text-xs text-muted-foreground font-medium">Footprint ID</dt>
            <dd className="text-sm mt-0.5 font-mono">{data.footprint_id}</dd>
          </div>
          <div className="py-1.5">
            <dt className="text-xs text-muted-foreground font-medium">Match Method</dt>
            <dd className="text-sm mt-0.5 capitalize">{data.method}</dd>
          </div>
          {data.area_sqm != null && (
            <div className="py-1.5">
              <dt className="text-xs text-muted-foreground font-medium">Building Area</dt>
              <dd className="text-sm mt-0.5">
                {data.area_sqm.toLocaleString()} m&sup2;
                {" "}({(data.area_sqm * 10.764).toLocaleString(undefined, { maximumFractionDigits: 0 })} SF)
              </dd>
            </div>
          )}
          {data.building_type && (
            <div className="py-1.5">
              <dt className="text-xs text-muted-foreground font-medium">Building Type</dt>
              <dd className="text-sm mt-0.5 capitalize">{data.building_type}</dd>
            </div>
          )}
          {data.building_name && (
            <div className="py-1.5">
              <dt className="text-xs text-muted-foreground font-medium">Building Name</dt>
              <dd className="text-sm mt-0.5">{data.building_name}</dd>
            </div>
          )}
        </dl>
      </CardContent>
    </Card>
  );
}

function ParcelCard({ propId }: { propId: string }) {
  const [data, setData] = useState<{
    parcel_id: string;
    municipality: string;
    pin: string | null;
    arn: string | null;
    address: string | null;
    city: string | null;
    zone_code: string | null;
    zone_desc: string | null;
    area_sqm: number | null;
    assessment: number | null;
    property_use: string | null;
    legal_desc: string | null;
    parcel_group: string[];
    parcel_brands: string[];
    parcel_building_count: number | null;
  } | null>(null);
  const [status, setStatus] = useState<"loading" | "loaded" | "none">("loading");

  useEffect(() => {
    fetch(`/api/properties/${propId}/parcel`)
      .then((r) => {
        if (!r.ok) throw new Error("not found");
        return r.json();
      })
      .then((d) => {
        setData(d);
        setStatus("loaded");
      })
      .catch(() => setStatus("none"));
  }, [propId]);

  if (status === "none") return null;
  if (status === "loading") return null;
  if (!data) return null;

  return (
    <Card>
      <CardHeader className="border-b border-border">
        <CardTitle>Parcel Boundary</CardTitle>
      </CardHeader>
      <CardContent>
        <dl className="grid grid-cols-2 gap-x-6">
          <div className="py-1.5">
            <dt className="text-xs text-muted-foreground font-medium">Parcel ID</dt>
            <dd className="text-sm mt-0.5 font-mono">{data.parcel_id}</dd>
          </div>
          <div className="py-1.5">
            <dt className="text-xs text-muted-foreground font-medium">Municipality</dt>
            <dd className="text-sm mt-0.5 capitalize">{data.municipality}</dd>
          </div>
          {data.pin && (
            <div className="py-1.5">
              <dt className="text-xs text-muted-foreground font-medium">PIN</dt>
              <dd className="text-sm mt-0.5 font-mono">{data.pin}</dd>
            </div>
          )}
          {data.arn && (
            <div className="py-1.5">
              <dt className="text-xs text-muted-foreground font-medium">ARN</dt>
              <dd className="text-sm mt-0.5 font-mono">{data.arn}</dd>
            </div>
          )}
          {data.area_sqm != null && (
            <div className="py-1.5">
              <dt className="text-xs text-muted-foreground font-medium">Parcel Area</dt>
              <dd className="text-sm mt-0.5">
                {data.area_sqm.toLocaleString()} m&sup2;
                {" "}({(data.area_sqm * 10.764).toLocaleString(undefined, { maximumFractionDigits: 0 })} SF)
              </dd>
            </div>
          )}
          {data.zone_code && (
            <div className="py-1.5">
              <dt className="text-xs text-muted-foreground font-medium">Zoning</dt>
              <dd className="text-sm mt-0.5">
                {data.zone_code}
                {data.zone_desc && <span className="text-muted-foreground ml-1">({data.zone_desc})</span>}
              </dd>
            </div>
          )}
          {data.assessment != null && (
            <div className="py-1.5">
              <dt className="text-xs text-muted-foreground font-medium">Assessment</dt>
              <dd className="text-sm mt-0.5">${data.assessment.toLocaleString()}</dd>
            </div>
          )}
          {data.property_use && (
            <div className="py-1.5">
              <dt className="text-xs text-muted-foreground font-medium">Property Use</dt>
              <dd className="text-sm mt-0.5">{data.property_use}</dd>
            </div>
          )}
          {data.parcel_building_count != null && (
            <div className="py-1.5">
              <dt className="text-xs text-muted-foreground font-medium">Buildings on Parcel</dt>
              <dd className="text-sm mt-0.5">{data.parcel_building_count}</dd>
            </div>
          )}
          {data.legal_desc && (
            <div className="py-1.5 col-span-2">
              <dt className="text-xs text-muted-foreground font-medium">Legal Description</dt>
              <dd className="text-sm mt-0.5 text-muted-foreground">{data.legal_desc}</dd>
            </div>
          )}
        </dl>

        {data.parcel_group.length > 0 && (
          <div className="mt-3 pt-3 border-t border-border">
            <dt className="text-xs text-muted-foreground font-medium mb-1.5">
              Same Parcel ({data.parcel_group.length + 1} properties)
            </dt>
            <dd className="flex flex-wrap gap-1.5">
              {data.parcel_group.map((pid) => (
                <Link
                  key={pid}
                  to={`/properties/${pid}`}
                  className="text-xs font-mono px-2 py-0.5 rounded bg-muted hover:bg-accent transition-colors"
                >
                  {pid}
                </Link>
              ))}
            </dd>
          </div>
        )}

        {data.parcel_brands.length > 0 && (
          <div className="mt-3 pt-3 border-t border-border">
            <dt className="text-xs text-muted-foreground font-medium mb-1.5">Brands on Parcel</dt>
            <dd className="flex flex-wrap gap-1.5">
              {data.parcel_brands.map((brand) => (
                <Badge key={brand} variant="secondary" className="text-xs">
                  {brand}
                </Badge>
              ))}
            </dd>
          </div>
        )}
      </CardContent>
    </Card>
  );
}

export default function PropertyDetailPage() {
  const { propId } = useParams<{ propId: string }>();
  const { data, loading, error, reload } = useProperty(propId!);
  const navigate = useNavigate();

  // Edit mode state
  const [editing, setEditing] = useState(false);
  const [saving, setSaving] = useState(false);
  const [saved, setSaved] = useState(false);
  const [editAddress, setEditAddress] = useState("");
  const [editCity, setEditCity] = useState("");
  const [editMunicipality, setEditMunicipality] = useState("");
  const [editProvince, setEditProvince] = useState("");
  const [editPostalCode, setEditPostalCode] = useState("");
  const [editLat, setEditLat] = useState("");
  const [editLng, setEditLng] = useState("");

  // Auto-dismiss saved feedback
  useEffect(() => {
    if (!saved) return;
    const t = setTimeout(() => setSaved(false), 2000);
    return () => clearTimeout(t);
  }, [saved]);

  const startEdit = () => {
    if (!data) return;
    setEditAddress(data.address || "");
    setEditCity(data.city || "");
    setEditMunicipality(data.municipality || "");
    setEditProvince(data.province || "");
    setEditPostalCode(data.postal_code || "");
    setEditLat(data.lat != null ? String(data.lat) : "");
    setEditLng(data.lng != null ? String(data.lng) : "");
    setEditing(true);
    setSaved(false);
  };

  const cancelEdit = () => {
    setEditing(false);
  };

  const saveEdit = async () => {
    if (!data) return;
    setSaving(true);
    try {
      const fields: Record<string, string | number> = {};
      if (editAddress.trim() !== (data.address || "")) fields.address = editAddress.trim();
      if (editCity.trim() !== (data.city || "")) fields.city = editCity.trim();
      if (editMunicipality.trim() !== (data.municipality || "")) fields.municipality = editMunicipality.trim();
      if (editProvince.trim() !== (data.province || "")) fields.province = editProvince.trim();
      if (editPostalCode.trim() !== (data.postal_code || "")) fields.postal_code = editPostalCode.trim();
      const latNum = editLat.trim() ? parseFloat(editLat.trim()) : null;
      const lngNum = editLng.trim() ? parseFloat(editLng.trim()) : null;
      if (latNum != null && !isNaN(latNum) && latNum !== data.lat) fields.lat = latNum;
      if (lngNum != null && !isNaN(lngNum) && lngNum !== data.lng) fields.lng = lngNum;

      if (Object.keys(fields).length === 0) {
        setEditing(false);
        return;
      }

      await updateProperty(data.prop_id, fields);
      setEditing(false);
      setSaved(true);
      reload();
    } catch (err) {
      console.error("Failed to save property:", err);
      alert(err instanceof Error ? err.message : "Failed to save");
    } finally {
      setSaving(false);
    }
  };

  if (loading) {
    return (
      <div className="flex items-center justify-center h-screen">
        <div className="text-muted-foreground">Loading...</div>
      </div>
    );
  }

  if (error || !data) {
    return (
      <div className="flex items-center justify-center h-screen">
        <div className="text-destructive">{error || "Property not found"}</div>
      </div>
    );
  }

  return (
    <div className="max-w-5xl mx-auto px-6 py-6">
      {/* Back link */}
      <Button
        variant="ghost"
        size="sm"
        className="mb-4 -ml-2"
        onClick={() => navigate(-1)}
      >
        <ArrowLeft size={16} />
        Back to properties
      </Button>

      {/* Header */}
      <div className="mb-6">
        <div className="flex items-center gap-2">
          <h1 className="text-2xl font-semibold">{data.address}</h1>
          <MapLink address={`${data.address}, ${data.city}`} lat={data.lat} lng={data.lng} size={16} />
          {data.brands?.map((brand) => (
            <Badge key={brand} variant="secondary">
              {brand}
            </Badge>
          ))}
          {data.linked_operators?.map((op) => (
            <a key={op.op_id} href={`/app/operators/${op.op_id}`}>
              <Badge variant="outline" className="text-blue-600 border-blue-300 hover:bg-blue-50 cursor-pointer">
                {op.name}
              </Badge>
            </a>
          ))}
        </div>
        {data.transactions[0]?.buyer && (
          <div className="mt-1">
            <p className="text-sm">
              Owner:{" "}
              {data.transactions[0].buyer_group_id ? (
                <Link
                  to={`/parties/${data.transactions[0].buyer_group_id}`}
                  className="text-primary hover:underline"
                >
                  {data.transactions[0].buyer}
                </Link>
              ) : (
                data.transactions[0].buyer
              )}
            </p>
            {(data.transactions[0].buyer_contact || data.transactions[0].buyer_phone) && (
              <p className="text-sm text-muted-foreground">
                {data.transactions[0].buyer_contact && data.transactions[0].buyer_contact_id ? (
                  <Link
                    to={`/contacts/${encodeURIComponent(data.transactions[0].buyer_contact_id)}`}
                    className="text-primary hover:underline"
                  >
                    {data.transactions[0].buyer_contact}
                  </Link>
                ) : (
                  data.transactions[0].buyer_contact
                )}
                {data.transactions[0].buyer_contact && data.transactions[0].buyer_phone && " \u2022 "}
                {data.transactions[0].buyer_phone}
              </p>
            )}
          </div>
        )}
        <p className="text-sm text-muted-foreground mt-0.5">
          {data.prop_id}
          {data.city && ` \u2022 ${data.city}`}
          {data.municipality && ` \u2022 ${data.municipality}`}
          {` \u2022 ${data.transaction_count} transaction${data.transaction_count !== 1 ? "s" : ""}`}
        </p>
      </div>

      <div className="space-y-5">
        {/* Photos + Location — side by side when photos exist */}
        {(() => {
          const recentWithPhotos = data.transactions.find(
            (tx) => tx.photos?.length > 0
          );
          const locationCard = (
            <Card>
              <CardHeader className="border-b border-border">
                <div className="flex items-center justify-between">
                  <CardTitle>Location</CardTitle>
                  <div className="flex items-center gap-2">
                    {saved && (
                      <span className="text-xs text-green-600 font-medium">Saved</span>
                    )}
                    {!editing && (
                      <Button variant="ghost" size="sm" onClick={startEdit} className="h-auto px-2 py-1">
                        <PencilSimple size={14} />
                        Edit
                      </Button>
                    )}
                  </div>
                </div>
              </CardHeader>
              <CardContent>
                {editing ? (
                  <div className="space-y-3">
                    <div className={recentWithPhotos ? "space-y-3" : "grid grid-cols-2 gap-x-4 gap-y-3"}>
                      <div>
                        <label className="text-xs font-medium text-muted-foreground">Address</label>
                        <Input value={editAddress} onChange={(e) => setEditAddress(e.target.value)} className="mt-1" />
                      </div>
                      <div>
                        <label className="text-xs font-medium text-muted-foreground">City</label>
                        <Input value={editCity} onChange={(e) => setEditCity(e.target.value)} className="mt-1" />
                      </div>
                      <div>
                        <label className="text-xs font-medium text-muted-foreground">Municipality</label>
                        <Input value={editMunicipality} onChange={(e) => setEditMunicipality(e.target.value)} className="mt-1" />
                      </div>
                      <div>
                        <label className="text-xs font-medium text-muted-foreground">Province</label>
                        <Input value={editProvince} onChange={(e) => setEditProvince(e.target.value)} className="mt-1" />
                      </div>
                      <div>
                        <label className="text-xs font-medium text-muted-foreground">Postal Code</label>
                        <Input value={editPostalCode} onChange={(e) => setEditPostalCode(e.target.value)} className="mt-1" />
                      </div>
                      <div>
                        <label className="text-xs font-medium text-muted-foreground">Coordinates</label>
                        <div className="flex gap-2 mt-1">
                          <Input value={editLat} onChange={(e) => setEditLat(e.target.value)} placeholder="Lat" className="flex-1" />
                          <Input value={editLng} onChange={(e) => setEditLng(e.target.value)} placeholder="Lng" className="flex-1" />
                        </div>
                      </div>
                    </div>
                    <div className="flex gap-2 justify-end pt-1">
                      <Button variant="outline" size="sm" onClick={cancelEdit}>
                        <X size={14} />
                        Cancel
                      </Button>
                      <Button size="sm" onClick={saveEdit} disabled={saving}>
                        <FloppyDisk size={14} />
                        {saving ? "Saving..." : "Save"}
                      </Button>
                    </div>
                  </div>
                ) : (
                  <dl className={recentWithPhotos ? "" : "grid grid-cols-2 gap-x-6"}>
                    <Field label="Address" value={data.address} />
                    <Field label="City" value={data.city} />
                    <Field label="Municipality" value={data.municipality} />
                    <Field label="Province" value={data.province} />
                    <Field label="Postal Code" value={data.postal_code} />
                    {data.lat != null && data.lng != null && (
                      <Field
                        label="Coordinates"
                        value={`${data.lat.toFixed(6)}, ${data.lng.toFixed(6)}`}
                      />
                    )}
                    <div className="py-1.5">
                      <dt className="text-xs text-muted-foreground font-medium">Sources</dt>
                      <dd className="text-sm mt-0.5">
                        {data.sources.map((src, i) => (
                          <span key={src}>
                            {i > 0 && ", "}
                            {src === "rt" && data.transactions.length > 0 ? (
                              <a
                                href={`/api/html/${data.transactions[0].rt_id}`}
                                target="_blank"
                                rel="noopener noreferrer"
                                className="text-primary hover:underline"
                              >
                                {src}
                              </a>
                            ) : (
                              src
                            )}
                          </span>
                        ))}
                      </dd>
                    </div>
                    <Field label="First Indexed" value={data.created} />
                  </dl>
                )}
              </CardContent>
            </Card>
          );

          if (!recentWithPhotos) return locationCard;

          const photos = recentWithPhotos.photos;
          return (
            <div className="grid grid-cols-2 gap-5">
              <Card>
                <CardHeader className="border-b border-border">
                  <CardTitle>Latest Photos ({recentWithPhotos.sale_date})</CardTitle>
                </CardHeader>
                <CardContent>
                  <div className="space-y-2">
                    <a
                      href={photos[0]}
                      target="_blank"
                      rel="noopener noreferrer"
                      className="block aspect-video bg-muted overflow-hidden hover:ring-2 hover:ring-ring transition"
                    >
                      <img
                        src={photos[0]}
                        alt="Photo 1"
                        className="w-full h-full object-cover"
                      />
                    </a>
                    {photos.length > 1 && (
                      <div className="grid grid-cols-4 gap-2">
                        {photos.slice(1, 5).map((url, i) => (
                          <a
                            key={i}
                            href={url}
                            target="_blank"
                            rel="noopener noreferrer"
                            className="block aspect-video bg-muted overflow-hidden hover:ring-2 hover:ring-ring transition"
                          >
                            <img
                              src={url}
                              alt={`Photo ${i + 2}`}
                              className="w-full h-full object-cover"
                              loading="lazy"
                            />
                          </a>
                        ))}
                      </div>
                    )}
                    {photos.length > 5 && (
                      <p className="text-xs text-muted-foreground text-right">
                        +{photos.length - 5} more below
                      </p>
                    )}
                  </div>
                </CardContent>
              </Card>
              {locationCard}
            </div>
          );
        })()}

        {/* Street View — on-demand, fetches and caches on first view */}
        {data.lat != null && data.lng != null && (
          <StreetViewCard propId={data.prop_id} />
        )}

        {/* Building Footprint */}
        <FootprintCard propId={data.prop_id} />

        {/* Parcel Boundary */}
        <ParcelCard propId={data.prop_id} />

        {/* GeoWarehouse Data */}
        {data.gw_records?.length > 0 && data.gw_records.map((gw: GWRecord) => (
          <div key={gw.gw_id} className="space-y-5">
            {/* Assessment & Registry */}
            <Card>
              <CardHeader className="border-b border-border">
                <CardTitle>Assessment & Registry ({gw.gw_id})</CardTitle>
              </CardHeader>
              <CardContent>
                <div className="grid grid-cols-2 gap-x-6">
                  <div>
                    <Field label="PIN" value={gw.registry?.pin} />
                    <Field label="ARN" value={gw.site_structure?.arn} />
                    <Field label="Assessed Value" value={gw.site_structure?.current_assessed_value} />
                    <Field label="Valuation Date" value={gw.site_structure?.valuation_date} />
                    <Field label="Zoning" value={gw.site_structure?.zoning} />
                    <Field label="Property Code" value={gw.site_structure?.property_code} />
                    <Field label="Frontage" value={gw.site_structure?.frontage} />
                    <Field label="Depth" value={gw.site_structure?.depth} />
                    <Field label="Site Area" value={gw.site_structure?.site_area} />
                    <Field label="Lot Size" value={gw.summary?.lot_size_area} />
                  </div>
                  <div>
                    <Field label="Property Type" value={gw.registry?.property_type} />
                    <Field label="Ownership Type" value={gw.registry?.ownership_type} />
                    <Field label="Registry Status" value={gw.registry?.land_registry_status} />
                    <Field label="Registration Type" value={gw.registry?.registration_type} />
                    <Field label="LRO" value={gw.registry?.land_registry_office} />
                    <Field label="Property Description" value={gw.site_structure?.property_description} />
                    <Field label="Legal Description" value={gw.summary?.legal_description} />
                  </div>
                </div>
              </CardContent>
            </Card>

            {/* Ownership */}
            <Card>
              <CardHeader className="border-b border-border">
                <CardTitle>Ownership (GeoWarehouse)</CardTitle>
              </CardHeader>
              <CardContent>
                <dl className="grid grid-cols-2 gap-x-6">
                  <Field label="Owner (Title)" value={gw.registry?.owner_names} />
                  <Field label="Owner (MPAC)" value={gw.site_structure?.owner_names_mpac} />
                  <Field label="Mailing Address" value={gw.site_structure?.owner_mailing_address} />
                </dl>
              </CardContent>
            </Card>

            {/* GW Sales History */}
            {gw.sales_history?.length > 0 && (
              <Card>
                <CardHeader className="border-b border-border">
                  <CardTitle>GW Sales History ({gw.sales_history.length})</CardTitle>
                </CardHeader>
                <CardContent>
                  <table className="w-full">
                    <thead>
                      <tr className="border-b border-border">
                        <th className="text-left text-[10px] font-medium text-muted-foreground uppercase py-2 pr-4">
                          Date
                        </th>
                        <th className="text-left text-[10px] font-medium text-muted-foreground uppercase py-2 pr-4">
                          Amount
                        </th>
                        <th className="text-left text-[10px] font-medium text-muted-foreground uppercase py-2 pr-4">
                          Type
                        </th>
                        <th className="text-left text-[10px] font-medium text-muted-foreground uppercase py-2">
                          Buyer
                        </th>
                      </tr>
                    </thead>
                    <tbody>
                      {gw.sales_history.map((sale, i) => (
                        <tr key={i} className="border-b border-border">
                          <td className="py-3 pr-4 text-xs">
                            {sale.sale_date}
                          </td>
                          <td className="py-3 pr-4 text-xs">
                            {sale.sale_amount}
                          </td>
                          <td className="py-3 pr-4 text-xs">
                            {sale.type}
                          </td>
                          <td className="py-3 text-xs">
                            {sale.party_to}
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </CardContent>
              </Card>
            )}
          </div>
        ))}

        {/* Outreach */}
        <PropertyOutreachCard
          propId={data.prop_id}
          address={data.address}
          city={data.city}
        />

        {/* Deals */}
        <PropertyDealCard
          propId={data.prop_id}
          address={data.address}
          city={data.city}
        />

        {/* Transaction History */}
        <Card>
          <CardHeader className="border-b border-border">
            <CardTitle>Transaction History ({data.transactions.length})</CardTitle>
          </CardHeader>
          <CardContent>
            {data.transactions.length === 0 ? (
              <p className="text-sm text-muted-foreground">No linked transactions.</p>
            ) : (
              <table className="w-full">
                <thead>
                  <tr className="border-b border-border">
                    <th className="text-left text-[10px] font-medium text-muted-foreground uppercase py-2 pr-4">
                      RT ID
                    </th>
                    <th className="text-left text-[10px] font-medium text-muted-foreground uppercase py-2 pr-4">
                      Sale Date
                    </th>
                    <th className="text-left text-[10px] font-medium text-muted-foreground uppercase py-2 pr-4">
                      Sale Price
                    </th>
                    <th className="text-left text-[10px] font-medium text-muted-foreground uppercase py-2 pr-4">
                      $/SF
                    </th>
                    <th className="text-left text-[10px] font-medium text-muted-foreground uppercase py-2 pr-4">
                      Seller
                    </th>
                    <th className="text-left text-[10px] font-medium text-muted-foreground uppercase py-2">
                      Buyer
                    </th>
                  </tr>
                </thead>
                <tbody>
                  {data.transactions.map((tx) => (
                    <tr
                      key={tx.rt_id}
                      className="border-b border-border hover:bg-muted/50 cursor-pointer transition-colors"
                      onClick={() => navigate(`/transactions/${tx.rt_id}`)}
                    >
                      <td className="py-3 pr-4 text-xs font-mono text-primary">
                        <span className="inline-flex items-center gap-1">
                          {tx.rt_id}
                          <a
                            href={`/api/html/${tx.rt_id}`}
                            target="_blank"
                            rel="noopener noreferrer"
                            className="text-muted-foreground hover:text-primary transition-colors"
                            onClick={(e) => e.stopPropagation()}
                            title="View source HTML"
                          >
                            <ArrowSquareOut size={12} />
                          </a>
                        </span>
                      </td>
                      <td className="py-3 pr-4 text-xs">
                        {tx.sale_date}
                      </td>
                      <td className="py-3 pr-4 text-xs">
                        {tx.sale_price}
                      </td>
                      <td className="py-3 pr-4 text-xs text-muted-foreground">
                        {tx.ppsf || "\u2014"}
                      </td>
                      <td className="py-3 pr-4 text-xs max-w-[200px] truncate">
                        {tx.seller_group_id ? (
                          <Link
                            to={`/parties/${tx.seller_group_id}`}
                            className="text-primary hover:underline"
                            onClick={(e) => e.stopPropagation()}
                          >
                            {tx.seller}
                          </Link>
                        ) : (
                          tx.seller
                        )}
                      </td>
                      <td className="py-3 text-xs max-w-[200px] truncate">
                        {tx.buyer_group_id ? (
                          <Link
                            to={`/parties/${tx.buyer_group_id}`}
                            className="text-primary hover:underline"
                            onClick={(e) => e.stopPropagation()}
                          >
                            {tx.buyer}
                          </Link>
                        ) : (
                          tx.buyer
                        )}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            )}
          </CardContent>
        </Card>

        {/* Photo History — all photos grouped by transaction */}
        {data.transactions.some((tx) => tx.photos?.length > 0) && (
          <Card>
            <CardHeader className="border-b border-border">
              <CardTitle>
                Photo History ({data.transactions.reduce(
                  (sum, tx) => sum + (tx.photos?.length || 0),
                  0
                )} photos)
              </CardTitle>
            </CardHeader>
            <CardContent>
              <div className="space-y-6">
                {data.transactions
                  .filter((tx) => tx.photos?.length > 0)
                  .map((tx) => (
                    <div key={tx.rt_id}>
                      <div className="flex items-baseline gap-2 mb-2">
                        <span className="text-sm font-medium">
                          {tx.sale_date}
                        </span>
                        <button
                          onClick={() => navigate(`/transactions/${tx.rt_id}`)}
                          className="text-xs font-mono text-primary hover:underline"
                        >
                          {tx.rt_id}
                        </button>
                        <span className="text-xs text-muted-foreground">
                          {tx.photos.length} photo{tx.photos.length !== 1 ? "s" : ""}
                        </span>
                      </div>
                      <div className="grid grid-cols-5 gap-2">
                        {tx.photos.map((url, i) => (
                          <a
                            key={i}
                            href={url}
                            target="_blank"
                            rel="noopener noreferrer"
                            className="block aspect-video bg-muted overflow-hidden hover:ring-2 hover:ring-ring transition"
                          >
                            <img
                              src={url}
                              alt={`${tx.rt_id} photo ${i + 1}`}
                              className="w-full h-full object-cover"
                              loading="lazy"
                            />
                          </a>
                        ))}
                      </div>
                    </div>
                  ))}
              </div>
            </CardContent>
          </Card>
        )}

        <DataIssueCard entityId={data.prop_id} />
      </div>
    </div>
  );
}
