import { useParams, useNavigate, Link } from "react-router-dom";
import { ArrowLeft } from "@phosphor-icons/react";
import { useParcel } from "../../api/parcels";
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

function formatPrice(price: number | null): string {
  if (price == null) return "--";
  return "$" + price.toLocaleString();
}

function formatArea(sqm: number | null): string {
  if (sqm == null) return "";
  const acres = sqm / 4046.86;
  if (acres >= 1) return `${acres.toFixed(2)} acres (${Math.round(sqm).toLocaleString()} sqm)`;
  return `${Math.round(sqm).toLocaleString()} sqm`;
}

export default function ParcelDetailPage() {
  const { arn } = useParams<{ arn: string }>();
  const navigate = useNavigate();
  const { data, loading, error } = useParcel(arn || "");

  if (loading) {
    return (
      <div className="flex items-center justify-center py-20">
        <p className="text-sm text-muted-foreground">Loading parcel...</p>
      </div>
    );
  }

  if (error || !data) {
    return (
      <div className="max-w-5xl mx-auto px-6 py-6">
        <Button variant="ghost" size="sm" onClick={() => navigate(-1)}>
          <ArrowLeft size={16} className="mr-1" />
          Back
        </Button>
        <p className="text-sm text-red-600 mt-4">
          {error || "Parcel not found"}
        </p>
      </div>
    );
  }

  return (
    <div className="max-w-5xl mx-auto px-6 py-6 space-y-5">
      {/* Back + Header */}
      <div>
        <Button variant="ghost" size="sm" onClick={() => navigate(-1)} className="mb-3">
          <ArrowLeft size={16} className="mr-1" />
          Back to Parcels
        </Button>
        <div className="flex items-start justify-between">
          <div>
            <h1 className="text-xl font-semibold">
              {data.addresses[0] || "Unnamed Parcel"}
            </h1>
            <p className="text-sm text-muted-foreground mt-1">
              {data.city}
              {data.population != null && ` (pop. ${data.population.toLocaleString()})`}
            </p>
            <div className="flex flex-wrap gap-1.5 mt-2">
              {data.pid && <Badge variant="outline">{data.pid}</Badge>}
              {data.sources.map((s) => (
                <Badge key={s} variant="secondary">{s}</Badge>
              ))}
            </div>
          </div>
        </div>
      </div>

      {/* Identifiers */}
      <Card>
        <CardHeader className="border-b border-border">
          <CardTitle>Parcel Identifiers</CardTitle>
        </CardHeader>
        <CardContent>
          <dl className="grid grid-cols-2 gap-x-6">
            <Field label="ARN (20-digit)" value={data.arn} />
            <Field label="PIN" value={data.pin || undefined} />
            <Field label="P-ID" value={data.pid || undefined} />
            <Field label="Discovered Via" value={data.discovered_via} />
            <Field label="Zoning" value={data.zoning || undefined} />
            <Field label="Area" value={formatArea(data.area_sqm)} />
          </dl>
          {data.addresses.length > 1 && (
            <div className="mt-3 pt-3 border-t border-border">
              <dt className="text-xs text-muted-foreground font-medium mb-1">All Addresses</dt>
              <dd className="space-y-0.5">
                {data.addresses.map((a, i) => (
                  <div key={i} className="text-sm">{a}</div>
                ))}
              </dd>
            </div>
          )}
        </CardContent>
      </Card>

      {/* Brands */}
      {data.brands.length > 0 && (
        <Card>
          <CardHeader className="border-b border-border">
            <CardTitle>
              Brands ({data.brands.length})
            </CardTitle>
          </CardHeader>
          <CardContent>
            <div className="flex flex-wrap gap-2">
              {data.brands.map((b, i) => (
                <Badge key={i} variant="secondary" className="text-xs">
                  {b.name}
                  {b.type && <span className="ml-1 text-muted-foreground">({b.type})</span>}
                </Badge>
              ))}
            </div>
          </CardContent>
        </Card>
      )}

      {/* Transactions */}
      {data.transactions.length > 0 && (
        <Card>
          <CardHeader className="border-b border-border">
            <CardTitle>
              Transaction History ({data.transactions.length})
            </CardTitle>
          </CardHeader>
          <CardContent className="p-0">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b border-border bg-muted/30">
                  <th className="text-left px-4 py-2 text-xs font-semibold uppercase tracking-widest text-muted-foreground">Date</th>
                  <th className="text-left px-4 py-2 text-xs font-semibold uppercase tracking-widest text-muted-foreground">Price</th>
                  <th className="text-left px-4 py-2 text-xs font-semibold uppercase tracking-widest text-muted-foreground">Buyer</th>
                  <th className="text-left px-4 py-2 text-xs font-semibold uppercase tracking-widest text-muted-foreground">Seller</th>
                  <th className="text-left px-4 py-2 text-xs font-semibold uppercase tracking-widest text-muted-foreground">ID</th>
                </tr>
              </thead>
              <tbody>
                {data.transactions.map((t, i) => (
                  <tr key={i} className="border-b border-border/50 hover:bg-muted/30">
                    <td className="px-4 py-2 tabular-nums">{t.date || "--"}</td>
                    <td className="px-4 py-2 tabular-nums font-medium">{formatPrice(t.price)}</td>
                    <td className="px-4 py-2">{t.buyer || "--"}</td>
                    <td className="px-4 py-2">{t.seller || "--"}</td>
                    <td className="px-4 py-2">
                      {t.rt_id.startsWith("GW:") ? (
                        <span className="font-mono text-xs">{t.rt_id}</span>
                      ) : (
                        <Link
                          to={`/transactions/${t.rt_id}`}
                          className="font-mono text-xs text-blue-600 hover:underline"
                        >
                          {t.rt_id}
                        </Link>
                      )}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </CardContent>
        </Card>
      )}

      {/* Assessment */}
      {data.assessment && (
        <Card>
          <CardHeader className="border-b border-border">
            <CardTitle>MPAC Assessment (GeoWarehouse)</CardTitle>
          </CardHeader>
          <CardContent>
            <dl className="grid grid-cols-2 gap-x-6">
              <Field label="Assessed Value" value={formatPrice(data.assessment.value)} />
              <Field label="Property Code" value={data.assessment.property_code || undefined} />
              <Field label="Property Description" value={data.assessment.property_description || undefined} />
              <Field label="Zoning" value={data.assessment.zoning || undefined} />
              <Field label="Frontage" value={data.assessment.frontage || undefined} />
              <Field label="Owner" value={data.assessment.owner || undefined} />
              <Field label="Owner Address" value={data.assessment.owner_address || undefined} />
            </dl>
            {data.assessment.legal_desc && (
              <div className="mt-3 pt-3 border-t border-border">
                <dt className="text-xs text-muted-foreground font-medium mb-1">Legal Description</dt>
                <dd className="text-xs font-mono whitespace-pre-wrap">{data.assessment.legal_desc}</dd>
              </div>
            )}
          </CardContent>
        </Card>
      )}
    </div>
  );
}
