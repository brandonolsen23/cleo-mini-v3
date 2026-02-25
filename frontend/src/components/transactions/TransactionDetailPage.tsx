import { useParams, useNavigate, Link } from "react-router-dom";
import { ArrowLeft } from "@phosphor-icons/react";
import { useTransaction } from "../../api/transactions";
import type { PartyInfo } from "../../types/transaction";
import DataIssueCard from "../shared/DataIssueCard";
import MapLink from "../shared/MapLink";
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

function PartyCard({ title, party }: { title: string; party: PartyInfo }) {
  return (
    <Card>
      <CardHeader className="border-b border-border">
        <CardTitle>{title}</CardTitle>
      </CardHeader>
      <CardContent>
        <dl className="grid grid-cols-2 gap-x-6">
          <div className="py-1.5">
            <dt className="text-xs text-muted-foreground font-medium">Name</dt>
            <dd className="text-sm mt-0.5">
              {party.group_id ? (
                <Link
                  to={`/parties/${party.group_id}`}
                  className="text-primary hover:underline"
                >
                  {party.name}
                </Link>
              ) : (
                party.name
              )}
            </dd>
          </div>
          {party.contact ? (
            <div className="py-1.5">
              <dt className="text-xs text-muted-foreground font-medium">Contact</dt>
              <dd className="text-sm mt-0.5">
                {party.contact_id ? (
                  <Link
                    to={`/contacts/${encodeURIComponent(party.contact_id)}`}
                    className="text-primary hover:underline"
                  >
                    {party.contact}
                  </Link>
                ) : (
                  party.contact
                )}
              </dd>
            </div>
          ) : null}
          <Field label="Phone" value={party.phone} />
          <Field label="Address" value={party.address} />
          {party.attention && <Field label="Attention" value={party.attention} />}
          {party.alternate_names?.length > 0 && (
            <Field
              label="Alternate Names"
              value={party.alternate_names.join("; ")}
            />
          )}
        </dl>
      </CardContent>
    </Card>
  );
}

export default function TransactionDetailPage() {
  const { rtId } = useParams<{ rtId: string }>();
  const { data, loading, error } = useTransaction(rtId!);
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
        <div className="text-destructive">
          {error || "Transaction not found"}
        </div>
      </div>
    );
  }

  const tx = data.transaction;
  const addr = tx.address;

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
        Back to transactions
      </Button>

      {/* Header */}
      <div className="mb-6">
        <div className="flex items-center gap-2">
          <h1 className="text-2xl font-semibold">
            {addr.address || data.rt_id}
          </h1>
          {addr.address && <MapLink address={`${addr.address}, ${addr.city}`} size={16} />}
          {data.brands?.map((brand) => (
            <Badge key={brand} variant="secondary">
              {brand}
            </Badge>
          ))}
        </div>
        <p className="text-sm text-muted-foreground mt-1">
          {data.rt_id}
          {addr.city && ` \u2022 ${addr.city}`}
          {tx.sale_date && ` \u2022 ${tx.sale_date}`}
          {tx.sale_price && ` \u2022 ${tx.sale_price}`}
        </p>
      </div>

      <div className="space-y-5">
        {/* Photos + Property — side by side when photos exist */}
        {data.photos?.length > 0 ? (
          <div className="grid grid-cols-2 gap-5">
            <Card>
              <CardHeader className="border-b border-border">
                <CardTitle>Photos</CardTitle>
              </CardHeader>
              <CardContent>
                <div className="space-y-2">
                  <a
                    href={data.photos[0]}
                    target="_blank"
                    rel="noopener noreferrer"
                    className="block aspect-video bg-muted overflow-hidden hover:ring-2 hover:ring-ring transition"
                  >
                    <img
                      src={data.photos[0]}
                      alt="Photo 1"
                      className="w-full h-full object-cover"
                    />
                  </a>
                  {data.photos.length > 1 && (
                    <div className="grid grid-cols-4 gap-2">
                      {data.photos.slice(1, 5).map((url, i) => (
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
                  {data.photos.length > 5 && (
                    <p className="text-xs text-muted-foreground text-right">
                      +{data.photos.length - 5} more
                    </p>
                  )}
                </div>
              </CardContent>
            </Card>
            <Card>
              <CardHeader className="border-b border-border">
                <CardTitle>Property</CardTitle>
              </CardHeader>
              <CardContent>
                <dl>
                  <Field label="Address" value={addr.address} />
                  <Field label="Suite" value={addr.address_suite} />
                  <Field label="City" value={addr.city} />
                  <Field label="Municipality" value={addr.municipality} />
                  <Field label="Province" value={addr.province} />
                  <Field label="Postal Code" value={addr.postal_code} />
                  <Field label="RT Number" value={tx.rt_number} />
                  <Field label="ARN" value={tx.arn} />
                  {tx.pins?.length > 0 && (
                    <Field label="PINs" value={tx.pins.join(", ")} />
                  )}
                  {addr.alternate_addresses?.length > 0 && (
                    <Field
                      label="Alternate Addresses"
                      value={addr.alternate_addresses.join("; ")}
                    />
                  )}
                </dl>
              </CardContent>
            </Card>
          </div>
        ) : (
          <Card>
            <CardHeader className="border-b border-border">
              <CardTitle>Property</CardTitle>
            </CardHeader>
            <CardContent>
              <dl className="grid grid-cols-2 gap-x-6">
                <Field label="Address" value={addr.address} />
                <Field label="Suite" value={addr.address_suite} />
                <Field label="City" value={addr.city} />
                <Field label="Municipality" value={addr.municipality} />
                <Field label="Province" value={addr.province} />
                <Field label="Postal Code" value={addr.postal_code} />
                <Field label="RT Number" value={tx.rt_number} />
                <Field label="ARN" value={tx.arn} />
                {tx.pins?.length > 0 && (
                  <Field label="PINs" value={tx.pins.join(", ")} />
                )}
                {addr.alternate_addresses?.length > 0 && (
                  <Field
                    label="Alternate Addresses"
                    value={addr.alternate_addresses.join("; ")}
                  />
                )}
              </dl>
            </CardContent>
          </Card>
        )}

        {/* Sale */}
        <Card>
          <CardHeader className="border-b border-border">
            <CardTitle>Sale</CardTitle>
          </CardHeader>
          <CardContent>
            <dl className="grid grid-cols-2 gap-x-6">
              <Field label="Sale Date" value={tx.sale_date} />
              <Field label="Sale Price" value={tx.sale_price} />
              {data.export_extras?.building_sf && (
                <Field label="Building Size" value={`${parseInt(data.export_extras.building_sf).toLocaleString()} sf`} />
              )}
              {data.ppsf && (
                <Field label="Price/SF" value={data.ppsf} />
              )}
            </dl>
          </CardContent>
        </Card>

        {/* Parties */}
        <div className="grid grid-cols-2 gap-5">
          <PartyCard title="Seller" party={data.transferor} />
          <PartyCard title="Buyer" party={data.transferee} />
        </div>

        {/* Site Details */}
        {data.site && (
          <Card>
            <CardHeader className="border-b border-border">
              <CardTitle>Site Details</CardTitle>
            </CardHeader>
            <CardContent>
              <dl className="grid grid-cols-2 gap-x-6">
                <Field
                  label="Legal Description"
                  value={data.site.legal_description}
                />
                <Field
                  label="Site Area"
                  value={
                    data.site.site_area
                      ? `${data.site.site_area} ${data.site.site_area_units}`
                      : undefined
                  }
                />
                <Field
                  label="Frontage"
                  value={
                    data.site.site_frontage
                      ? `${data.site.site_frontage} ${data.site.site_frontage_units}`
                      : undefined
                  }
                />
                <Field
                  label="Depth"
                  value={
                    data.site.site_depth
                      ? `${data.site.site_depth} ${data.site.site_depth_units}`
                      : undefined
                  }
                />
                <Field label="Zoning" value={data.site.zoning} />
                {data.site.pins?.length > 0 && (
                  <Field label="PINs" value={data.site.pins.join(", ")} />
                )}
              </dl>
            </CardContent>
          </Card>
        )}

        {/* Consideration */}
        {data.consideration && (
          <Card>
            <CardHeader className="border-b border-border">
              <CardTitle>Consideration</CardTitle>
            </CardHeader>
            <CardContent>
              <dl className="grid grid-cols-2 gap-x-6">
                <Field
                  label="Cash"
                  value={
                    data.consideration.cash
                      ? `$${Number(data.consideration.cash).toLocaleString()}`
                      : undefined
                  }
                />
                <Field
                  label="Assumed Debt"
                  value={
                    data.consideration.assumed_debt &&
                    data.consideration.assumed_debt !== "0"
                      ? `$${Number(data.consideration.assumed_debt).toLocaleString()}`
                      : undefined
                  }
                />
                <Field label="Chattels" value={data.consideration.chattels} />
                {data.consideration.chargees?.length > 0 && (
                  <Field
                    label="Chargees"
                    value={data.consideration.chargees.join("; ")}
                  />
                )}
              </dl>
            </CardContent>
          </Card>
        )}

        {/* Broker */}
        {data.broker?.brokerage && (
          <Card>
            <CardHeader className="border-b border-border">
              <CardTitle>Broker</CardTitle>
            </CardHeader>
            <CardContent>
              <dl className="grid grid-cols-2 gap-x-6">
                <Field label="Brokerage" value={data.broker.brokerage} />
                <Field label="Phone" value={data.broker.phone} />
              </dl>
            </CardContent>
          </Card>
        )}

        {/* Description */}
        {data.description && (
          <Card>
            <CardHeader className="border-b border-border">
              <CardTitle>Description</CardTitle>
            </CardHeader>
            <CardContent>
              <p className="text-sm whitespace-pre-wrap">
                {data.description}
              </p>
            </CardContent>
          </Card>
        )}

        <DataIssueCard entityId={data.rt_id} />
      </div>
    </div>
  );
}
