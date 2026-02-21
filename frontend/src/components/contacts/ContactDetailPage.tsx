import { useState } from "react";
import { useParams, useNavigate } from "react-router-dom";
import { ArrowLeft, CaretDown, CaretUp } from "@phosphor-icons/react";
import { useContact } from "../../api/contacts";
import { useCrmContactByComputed, createCrmContact } from "../../api/crm";
import { Card, CardHeader, CardTitle, CardContent } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { cn } from "@/lib/utils";

const COLLAPSED_LIMIT = 5;

function ShowMore({
  total,
  expanded,
  onToggle,
}: {
  total: number;
  expanded: boolean;
  onToggle: () => void;
}) {
  if (total <= COLLAPSED_LIMIT) return null;
  return (
    <Button
      variant="ghost"
      size="sm"
      onClick={onToggle}
      className="h-auto px-0 py-0 mt-2 text-xs font-medium text-muted-foreground hover:text-foreground hover:bg-transparent"
    >
      {expanded ? (
        <>
          <CaretUp size={14} />
          Show less
        </>
      ) : (
        <>
          <CaretDown size={14} />
          Show all {total.toLocaleString()}
        </>
      )}
    </Button>
  );
}

function RoleBadge({ role }: { role: string }) {
  const isBuyer = role === "buyer";
  return (
    <span
      className={cn(
        "inline-flex items-center px-2 py-0.5 rounded text-xs font-medium",
        isBuyer
          ? "bg-green-100 text-green-700"
          : "bg-orange-100 text-orange-700"
      )}
    >
      {isBuyer ? "Buyer" : "Seller"}
    </span>
  );
}

export default function ContactDetailPage() {
  const { contactId } = useParams<{ contactId: string }>();
  const { data, loading, error } = useContact(contactId!);
  const navigate = useNavigate();

  const [txnsExpanded, setTxnsExpanded] = useState(false);
  const [entitiesExpanded, setEntitiesExpanded] = useState(false);
  const [creatingCrm, setCreatingCrm] = useState(false);

  // Check if a CRM contact exists for this computed contact
  const { data: crmContact, notFound: noCrm } = useCrmContactByComputed(
    data?.contact_id,
  );

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
        <div className="text-destructive">{error || "Contact not found"}</div>
      </div>
    );
  }

  const visibleTxns = txnsExpanded ? data.appearances : data.appearances.slice(0, COLLAPSED_LIMIT);
  const visibleEntities = entitiesExpanded ? data.entities : data.entities.slice(0, COLLAPSED_LIMIT);

  return (
    <div className="max-w-5xl mx-auto px-6 py-6">
      {/* Back link */}
      <Button
        variant="ghost"
        size="sm"
        onClick={() => navigate(-1)}
        className="h-auto px-0 py-0 text-sm text-muted-foreground hover:text-foreground hover:bg-transparent mb-4"
      >
        <ArrowLeft size={16} />
        Back to contacts
      </Button>

      {/* Header */}
      <div className="mb-6">
        <h1 className="text-2xl font-semibold text-foreground">
          {data.name}
        </h1>
        <p className="text-sm text-muted-foreground mt-1">
          {data.transaction_count} transaction{data.transaction_count !== 1 ? "s" : ""}
          {` \u2022 ${data.entity_count} entit${data.entity_count !== 1 ? "ies" : "y"}`}
          {data.first_active_iso && data.last_active_iso && (
            <>
              {" \u2022 "}
              {data.first_active_iso.slice(0, 4)}&ndash;
              {data.last_active_iso.slice(0, 4)}
            </>
          )}
        </p>
      </div>

      <div className="space-y-5">
        {/* CRM Enrichment Card */}
        <Card>
          <CardHeader className="px-5 py-3 border-b border-border">
            <CardTitle className="text-sm font-semibold uppercase tracking-wider">
              CRM Profile
            </CardTitle>
          </CardHeader>
          <CardContent className="px-5 py-4">
            {crmContact ? (
              <div className="flex items-center justify-between">
                <div>
                  <div className="flex items-center gap-2">
                    <span className="text-sm font-medium">{crmContact.name}</span>
                    <Badge variant="outline" className="text-[10px] font-mono">{crmContact.crm_id}</Badge>
                  </div>
                  <div className="text-xs text-muted-foreground mt-0.5">
                    {[crmContact.email, crmContact.mobile].filter(Boolean).join(" \u2022 ") || "No contact info"}
                  </div>
                </div>
                <Button
                  size="sm"
                  variant="outline"
                  onClick={() => navigate(`/crm/contacts/${crmContact.crm_id}`)}
                >
                  View CRM Profile
                </Button>
              </div>
            ) : noCrm ? (
              <div className="flex items-center justify-between">
                <p className="text-sm text-muted-foreground">
                  No CRM contact linked to this person.
                </p>
                <Button
                  size="sm"
                  disabled={creatingCrm}
                  onClick={async () => {
                    setCreatingCrm(true);
                    try {
                      const result = await createCrmContact({
                        name: data.name,
                        computed_contact_id: data.contact_id,
                      });
                      navigate(`/crm/contacts/${result.crm_id}`);
                    } finally {
                      setCreatingCrm(false);
                    }
                  }}
                >
                  {creatingCrm ? "Creating..." : "Create CRM Contact"}
                </Button>
              </div>
            ) : (
              <p className="text-sm text-muted-foreground">Checking CRM...</p>
            )}
          </CardContent>
        </Card>

        {/* Info Card */}
        {(data.phones.length > 0 || data.addresses.length > 0) && (
          <Card>
            <CardHeader className="px-5 py-3 border-b border-border">
              <CardTitle className="text-sm font-semibold uppercase tracking-wider">
                Contact Info
              </CardTitle>
            </CardHeader>
            <CardContent className="px-5 py-4">
              <div className="grid grid-cols-2 gap-x-6 gap-y-3">
                {data.phones.length > 0 && (
                  <div>
                    <dt className="text-xs text-muted-foreground font-medium mb-1">
                      Phones
                    </dt>
                    <dd className="space-y-0.5">
                      {data.phones.map((p, i) => (
                        <div key={i} className="text-sm text-foreground">{p}</div>
                      ))}
                    </dd>
                  </div>
                )}
                {data.addresses.length > 0 && (
                  <div className={data.phones.length > 0 ? "" : "col-span-2"}>
                    <dt className="text-xs text-muted-foreground font-medium mb-1">
                      Addresses
                    </dt>
                    <dd className="space-y-0.5">
                      {data.addresses.map((a, i) => (
                        <div key={i} className="text-sm text-foreground">{a}</div>
                      ))}
                    </dd>
                  </div>
                )}
              </div>
            </CardContent>
          </Card>
        )}

        {/* Party Groups */}
        {data.party_groups.length > 0 && (
          <Card>
            <CardHeader className="px-5 py-3 border-b border-border">
              <CardTitle className="text-sm font-semibold uppercase tracking-wider">
                Linked Party Groups ({data.party_groups.length})
              </CardTitle>
            </CardHeader>
            <CardContent className="px-5 py-4">
              <table className="w-full">
                <thead>
                  <tr className="border-b border-border">
                    <th className="text-left text-[10px] font-medium text-muted-foreground uppercase py-2 pr-4">
                      ID
                    </th>
                    <th className="text-left text-[10px] font-medium text-muted-foreground uppercase py-2 pr-4">
                      Display Name
                    </th>
                    <th className="text-left text-[10px] font-medium text-muted-foreground uppercase py-2">
                      Txns
                    </th>
                  </tr>
                </thead>
                <tbody>
                  {data.party_groups.map((pg) => (
                    <tr
                      key={pg.group_id}
                      className="border-b border-border hover:bg-accent cursor-pointer transition-colors"
                      onClick={() => navigate(`/parties/${pg.group_id}`)}
                    >
                      <td className="py-3 pr-4 text-xs font-mono text-primary">
                        {pg.group_id}
                      </td>
                      <td className="py-3 pr-4 text-xs text-foreground">
                        {pg.display_name}
                      </td>
                      <td className="py-3 text-xs text-foreground">
                        {pg.transaction_count}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </CardContent>
          </Card>
        )}

        {/* Entities */}
        {data.entities.length > 0 && (
          <Card>
            <CardHeader className="px-5 py-3 border-b border-border">
              <CardTitle className="text-sm font-semibold uppercase tracking-wider">
                Entities ({data.entities.length})
              </CardTitle>
            </CardHeader>
            <CardContent className="px-5 py-4">
              <div className="space-y-0.5">
                {visibleEntities.map((e, i) => (
                  <div key={i} className="text-sm text-foreground">{e}</div>
                ))}
              </div>
              <ShowMore
                total={data.entities.length}
                expanded={entitiesExpanded}
                onToggle={() => setEntitiesExpanded(!entitiesExpanded)}
              />
            </CardContent>
          </Card>
        )}

        {/* Transaction History */}
        <Card>
          <CardHeader className="px-5 py-3 border-b border-border">
            <CardTitle className="text-sm font-semibold uppercase tracking-wider">
              Transaction History ({data.appearances.length})
            </CardTitle>
          </CardHeader>
          <CardContent className="px-5 py-4">
            {data.appearances.length === 0 ? (
              <p className="text-sm text-muted-foreground">No transactions found.</p>
            ) : (
              <>
                <table className="w-full">
                  <thead>
                    <tr className="border-b border-border">
                      <th className="text-left text-[10px] font-medium text-muted-foreground uppercase py-2 pr-4">
                        RT ID
                      </th>
                      <th className="text-left text-[10px] font-medium text-muted-foreground uppercase py-2 pr-4">
                        Role
                      </th>
                      <th className="text-left text-[10px] font-medium text-muted-foreground uppercase py-2 pr-4">
                        Entity
                      </th>
                      <th className="text-left text-[10px] font-medium text-muted-foreground uppercase py-2 pr-4">
                        Sale Date
                      </th>
                      <th className="text-left text-[10px] font-medium text-muted-foreground uppercase py-2 pr-4">
                        Sale Price
                      </th>
                      <th className="text-left text-[10px] font-medium text-muted-foreground uppercase py-2 pr-4">
                        Address
                      </th>
                      <th className="text-left text-[10px] font-medium text-muted-foreground uppercase py-2">
                        City
                      </th>
                    </tr>
                  </thead>
                  <tbody>
                    {visibleTxns.map((app, i) => (
                      <tr
                        key={`${app.rt_id}-${app.role}-${i}`}
                        className="border-b border-border hover:bg-accent cursor-pointer transition-colors"
                        onClick={() => navigate(`/transactions/${app.rt_id}`)}
                      >
                        <td className="py-3 pr-4 text-xs font-mono text-primary">
                          {app.rt_id}
                        </td>
                        <td className="py-3 pr-4">
                          <RoleBadge role={app.role} />
                        </td>
                        <td className="py-3 pr-4 text-xs text-foreground max-w-[180px] truncate">
                          {app.entity_name}
                        </td>
                        <td className="py-3 pr-4 text-xs text-foreground">
                          {app.sale_date_iso}
                        </td>
                        <td className="py-3 pr-4 text-xs text-foreground">
                          {app.sale_price}
                        </td>
                        <td className="py-3 pr-4 text-xs text-foreground max-w-[180px] truncate">
                          {app.prop_address}
                        </td>
                        <td className="py-3 text-xs text-foreground">
                          {app.prop_city}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
                <ShowMore
                  total={data.appearances.length}
                  expanded={txnsExpanded}
                  onToggle={() => setTxnsExpanded(!txnsExpanded)}
                />
              </>
            )}
          </CardContent>
        </Card>
      </div>
    </div>
  );
}
