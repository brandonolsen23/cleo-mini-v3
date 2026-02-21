import { useParams, useNavigate } from "react-router-dom";
import { ArrowLeft } from "@phosphor-icons/react";
import { useProperty } from "../../api/properties";
import DataIssueCard from "../shared/DataIssueCard";
import MapLink from "../shared/MapLink";
import PropertyDealCard from "../crm/PropertyDealCard";
import type { GWRecord } from "../../types/property";
import { Card, CardHeader, CardTitle, CardContent } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";

function Field({ label, value }: { label: string; value: string | undefined }) {
  if (!value) return null;
  return (
    <div className="py-1.5">
      <dt className="text-xs text-muted-foreground font-medium">{label}</dt>
      <dd className="text-sm mt-0.5">{value}</dd>
    </div>
  );
}

export default function PropertyDetailPage() {
  const { propId } = useParams<{ propId: string }>();
  const { data, loading, error } = useProperty(propId!);
  const navigate = useNavigate();

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
        </div>
        {data.transactions[0]?.buyer && (
          <div className="mt-1">
            <p className="text-sm">
              Owner: {data.transactions[0].buyer}
            </p>
            {(data.transactions[0].buyer_contact || data.transactions[0].buyer_phone) && (
              <p className="text-sm text-muted-foreground">
                {data.transactions[0].buyer_contact}
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
                <CardTitle>Location</CardTitle>
              </CardHeader>
              <CardContent>
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
                  <Field label="Sources" value={data.sources.join(", ")} />
                  <Field label="First Indexed" value={data.created} />
                </dl>
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
                        {tx.rt_id}
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
                        {tx.seller}
                      </td>
                      <td className="py-3 text-xs max-w-[200px] truncate">
                        {tx.buyer}
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
