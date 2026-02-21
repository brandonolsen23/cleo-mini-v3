import { useState, useEffect, useRef } from "react";
import { useParams, useNavigate } from "react-router-dom";
import { ArrowLeft, ArrowSquareOut, PencilSimple, Globe, Check, X, CaretDown, CaretUp, LinkBreak, CheckCircle } from "@phosphor-icons/react";
import { useParty } from "../../api/parties";
import DataIssueCard from "../shared/DataIssueCard";
import { Sheet, SheetContent, SheetHeader, SheetTitle, SheetDescription } from "@/components/ui/sheet";
import { Card, CardHeader, CardTitle, CardContent } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Input } from "@/components/ui/input";
import { cn } from "@/lib/utils";
import NameEvidenceDrawer from "./NameEvidenceDrawer";
import SuggestedAffiliates from "./SuggestedAffiliates";

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

function InlineNameEditor({
  displayName,
  displayNameAuto,
  saving,
  onSave,
}: {
  displayName: string;
  displayNameAuto: string;
  saving: boolean;
  onSave: (name: string) => void;
}) {
  const [editing, setEditing] = useState(false);
  const [value, setValue] = useState(displayName);
  const inputRef = useRef<HTMLInputElement>(null);

  useEffect(() => {
    setValue(displayName);
  }, [displayName]);

  useEffect(() => {
    if (editing) inputRef.current?.focus();
  }, [editing]);

  const handleSave = () => {
    onSave(value);
    setEditing(false);
  };

  const handleCancel = () => {
    setValue(displayName);
    setEditing(false);
  };

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === "Enter") handleSave();
    if (e.key === "Escape") handleCancel();
  };

  if (!editing) {
    return (
      <Button
        variant="ghost"
        size="icon"
        onClick={() => setEditing(true)}
        className="h-auto w-auto p-1 text-muted-foreground hover:text-foreground ml-2"
        title="Edit display name"
      >
        <PencilSimple size={14} />
      </Button>
    );
  }

  return (
    <div className="inline-flex items-center gap-2 ml-2">
      <Input
        ref={inputRef}
        type="text"
        value={value}
        onChange={(e) => setValue(e.target.value)}
        onKeyDown={handleKeyDown}
        placeholder={displayNameAuto}
        className="text-lg h-8 px-2 py-0.5 w-64"
      />
      <Button
        variant="ghost"
        size="icon"
        onClick={handleSave}
        disabled={saving}
        className="h-auto w-auto p-1 text-green-600 hover:text-green-800"
        title="Save"
      >
        <Check size={16} />
      </Button>
      <Button
        variant="ghost"
        size="icon"
        onClick={handleCancel}
        className="h-auto w-auto p-1 text-muted-foreground hover:text-foreground"
        title="Cancel"
      >
        <X size={16} />
      </Button>
    </div>
  );
}

function InlineUrlEditor({
  url,
  saving,
  onSave,
}: {
  url: string;
  saving: boolean;
  onSave: (url: string) => void;
}) {
  const [editing, setEditing] = useState(false);
  const [value, setValue] = useState(url);
  const inputRef = useRef<HTMLInputElement>(null);

  useEffect(() => {
    setValue(url);
  }, [url]);

  useEffect(() => {
    if (editing) inputRef.current?.focus();
  }, [editing]);

  const handleSave = () => {
    onSave(value);
    setEditing(false);
  };

  const handleCancel = () => {
    setValue(url);
    setEditing(false);
  };

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === "Enter") handleSave();
    if (e.key === "Escape") handleCancel();
  };

  if (!editing && url) {
    return (
      <>
        <a
          href={url}
          target="_blank"
          rel="noopener noreferrer"
          className="inline-flex items-center gap-1 text-sm text-primary hover:text-primary/80 transition-colors"
        >
          <ArrowSquareOut size={14} />
          Website
        </a>
        <Button
          variant="ghost"
          size="icon"
          onClick={() => setEditing(true)}
          className="h-auto w-auto p-1 text-muted-foreground hover:text-foreground"
          title="Edit URL"
        >
          <PencilSimple size={12} />
        </Button>
      </>
    );
  }

  if (!editing) {
    return (
      <Button
        variant="ghost"
        size="icon"
        onClick={() => setEditing(true)}
        className="h-auto w-auto p-1 text-muted-foreground hover:text-foreground"
        title="Add website URL"
      >
        <Globe size={14} />
      </Button>
    );
  }

  return (
    <div className="inline-flex items-center gap-2">
      <Input
        ref={inputRef}
        type="url"
        value={value}
        onChange={(e) => setValue(e.target.value)}
        onKeyDown={handleKeyDown}
        placeholder="https://www.example.com"
        className="text-sm h-8 px-2 py-0.5 w-64"
      />
      <Button
        variant="ghost"
        size="icon"
        onClick={handleSave}
        disabled={saving}
        className="h-auto w-auto p-1 text-green-600 hover:text-green-800"
        title="Save"
      >
        <Check size={16} />
      </Button>
      <Button
        variant="ghost"
        size="icon"
        onClick={handleCancel}
        className="h-auto w-auto p-1 text-muted-foreground hover:text-foreground"
        title="Cancel"
      >
        <X size={16} />
      </Button>
    </div>
  );
}

function DisconnectForm({
  name,
  saving,
  onDisconnect,
  onCancel,
}: {
  name: string;
  saving: boolean;
  onDisconnect: (targetGroup: string, reason: string) => void;
  onCancel: () => void;
}) {
  const [targetGroup, setTargetGroup] = useState("");
  const [reason, setReason] = useState("");
  const inputRef = useRef<HTMLInputElement>(null);

  useEffect(() => {
    inputRef.current?.focus();
  }, []);

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === "Enter") onDisconnect(targetGroup, reason);
    if (e.key === "Escape") onCancel();
  };

  return (
    <div className="ml-6 mt-1 mb-2 p-3 bg-muted rounded-lg border border-border text-sm space-y-2">
      <div className="text-xs text-muted-foreground font-medium">
        Disconnect "{name}" from this group
      </div>
      <div className="flex items-center gap-2">
        <label className="text-xs text-muted-foreground w-24 flex-none">Move to group</label>
        <input
          ref={inputRef}
          type="text"
          value={targetGroup}
          onChange={(e) => setTargetGroup(e.target.value)}
          onKeyDown={handleKeyDown}
          placeholder="G_____ (blank = new group)"
          className="flex-1 px-2 py-1 text-sm border border-border rounded bg-background focus:outline-none focus:ring-2 focus:ring-ring focus:border-transparent"
        />
      </div>
      <div className="flex items-center gap-2">
        <label className="text-xs text-muted-foreground w-24 flex-none">Reason</label>
        <input
          type="text"
          value={reason}
          onChange={(e) => setReason(e.target.value)}
          onKeyDown={handleKeyDown}
          placeholder="e.g. Different parent company"
          className="flex-1 px-2 py-1 text-sm border border-border rounded bg-background focus:outline-none focus:ring-2 focus:ring-ring focus:border-transparent"
        />
      </div>
      <div className="flex items-center gap-2">
        <Button
          variant="destructive"
          size="sm"
          onClick={() => onDisconnect(targetGroup, reason)}
          disabled={saving}
          className="text-xs"
        >
          {saving ? "Saving..." : "Disconnect"}
        </Button>
        <Button
          variant="outline"
          size="sm"
          onClick={onCancel}
          className="text-xs"
        >
          Cancel
        </Button>
      </div>
    </div>
  );
}

export default function PartyDetailPage() {
  const { groupId } = useParams<{ groupId: string }>();
  const { data, loading, error, saving, saved, saveOverrides, disconnectName, confirmName, reload } = useParty(
    groupId!
  );
  const navigate = useNavigate();

  const [disconnectingName, setDisconnectingName] = useState<string | null>(null);
  const [drawerName, setDrawerName] = useState<string | null>(null);
  const [namesExpanded, setNamesExpanded] = useState(false);
  const [aliasesExpanded, setAliasesExpanded] = useState(false);
  const [contactsExpanded, setContactsExpanded] = useState(false);
  const [phonesExpanded, setPhonesExpanded] = useState(false);
  const [addressesExpanded, setAddressesExpanded] = useState(false);
  const [txnsExpanded, setTxnsExpanded] = useState(false);
  const [propsExpanded, setPropsExpanded] = useState(false);

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
        <div className="text-destructive">{error || "Party group not found"}</div>
      </div>
    );
  }

  const handleNameSave = (name: string) => {
    saveOverrides({ display_name: name, url: data.url });
  };

  const handleUrlSave = (url: string) => {
    saveOverrides({ display_name: data.display_name_override, url });
  };

  const visibleNames = namesExpanded ? data.names : data.names.slice(0, COLLAPSED_LIMIT);
  const visibleAliases = aliasesExpanded ? data.aliases : data.aliases.slice(0, COLLAPSED_LIMIT);
  const visibleContacts = contactsExpanded ? data.contacts : data.contacts.slice(0, COLLAPSED_LIMIT);
  const visiblePhones = phonesExpanded ? data.phones : data.phones.slice(0, COLLAPSED_LIMIT);
  const visibleAddresses = addressesExpanded ? data.addresses : data.addresses.slice(0, COLLAPSED_LIMIT);
  const visibleTxns = txnsExpanded ? data.appearances : data.appearances.slice(0, COLLAPSED_LIMIT);
  const visibleProps = propsExpanded ? data.linked_properties : data.linked_properties.slice(0, COLLAPSED_LIMIT);

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
        Back to parties
      </Button>

      {/* Header */}
      <div className="mb-6">
        <div className="flex items-center gap-2 flex-wrap">
          <h1 className="text-2xl font-semibold text-foreground">
            {data.display_name}
          </h1>
          <InlineNameEditor
            displayName={data.display_name_override}
            displayNameAuto={data.display_name_auto}
            saving={saving}
            onSave={handleNameSave}
          />
          <Badge
            variant="secondary"
            className={cn(
              data.is_company
                ? "bg-secondary text-secondary-foreground"
                : "bg-muted text-muted-foreground"
            )}
          >
            {data.is_company ? "Company" : "Person"}
          </Badge>
          <InlineUrlEditor
            url={data.url}
            saving={saving}
            onSave={handleUrlSave}
          />
          {saved && <span className="text-xs text-green-600">Saved</span>}
        </div>
        <p className="text-sm text-muted-foreground mt-1">
          {data.group_id}
          {` \u2022 ${data.transaction_count} transaction${data.transaction_count !== 1 ? "s" : ""}`}
          {` \u2022 ${data.buy_count} buys, ${data.sell_count} sells`}
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
        {/* Identity Card */}
        <Card>
          <CardHeader className="px-5 py-3 border-b border-border">
            <CardTitle className="text-sm font-semibold uppercase tracking-wider">
              Identity ({data.names.length} name{data.names.length !== 1 ? "s" : ""})
            </CardTitle>
          </CardHeader>
          <CardContent className="px-5 py-4">
            <div className="space-y-3">
              <div>
                <dt className="text-xs text-muted-foreground font-medium mb-1">
                  Company Names
                </dt>
                <dd className="space-y-0.5">
                  {visibleNames.map((name, i) => {
                    const normName = name.toUpperCase().replace(/\s+/g, " ").trim();
                    const isConfirmed = data.confirmed_names.includes(normName);
                    return (
                      <div key={i}>
                        <div className="flex items-center gap-1.5 group">
                          <button
                            onClick={() => setDrawerName(name)}
                            className="text-sm text-foreground hover:text-primary hover:underline transition-colors text-left"
                          >
                            {name}
                          </button>
                          {isConfirmed && (
                            <span title="Confirmed"><CheckCircle size={14} className="text-green-500 flex-none" /></span>
                          )}
                          {data.names.length > 1 && (
                            <span className="opacity-0 group-hover:opacity-100 transition-opacity inline-flex items-center gap-0.5 ml-1">
                              {!isConfirmed && (
                                <Button
                                  variant="ghost"
                                  size="icon"
                                  onClick={() => confirmName(name)}
                                  disabled={saving}
                                  className="h-auto w-auto p-0.5 text-muted-foreground/50 hover:text-green-600 hover:bg-transparent"
                                  title="Confirm this name belongs here"
                                >
                                  <Check size={13} />
                                </Button>
                              )}
                              <Button
                                variant="ghost"
                                size="icon"
                                onClick={() => setDisconnectingName(disconnectingName === name ? null : name)}
                                disabled={saving}
                                className="h-auto w-auto p-0.5 text-muted-foreground/50 hover:text-destructive hover:bg-transparent"
                                title="Disconnect from this group"
                              >
                                <LinkBreak size={13} />
                              </Button>
                            </span>
                          )}
                        </div>
                        {disconnectingName === name && (
                          <DisconnectForm
                            name={name}
                            saving={saving}
                            onDisconnect={async (targetGroup, reason) => {
                              const result = await disconnectName(name, targetGroup, reason);
                              if (result) {
                                setDisconnectingName(null);
                              }
                            }}
                            onCancel={() => setDisconnectingName(null)}
                          />
                        )}
                      </div>
                    );
                  })}
                </dd>
                <ShowMore
                  total={data.names.length}
                  expanded={namesExpanded}
                  onToggle={() => setNamesExpanded(!namesExpanded)}
                />
              </div>
              {data.aliases.length > 0 && (
                <div>
                  <dt className="text-xs text-muted-foreground font-medium mb-1">
                    Aliases
                  </dt>
                  <dd className="flex flex-wrap gap-1.5">
                    {visibleAliases.map((alias, i) => (
                      <Badge
                        key={i}
                        variant="secondary"
                        className="text-xs font-normal"
                      >
                        {alias}
                      </Badge>
                    ))}
                  </dd>
                  <ShowMore
                    total={data.aliases.length}
                    expanded={aliasesExpanded}
                    onToggle={() => setAliasesExpanded(!aliasesExpanded)}
                  />
                </div>
              )}
            </div>
          </CardContent>
        </Card>

        {/* Contact Card */}
        {(data.contacts.length > 0 ||
          data.phones.length > 0 ||
          data.addresses.length > 0) && (
          <Card>
            <CardHeader className="px-5 py-3 border-b border-border">
              <CardTitle className="text-sm font-semibold uppercase tracking-wider">
                Contacts & Addresses
              </CardTitle>
            </CardHeader>
            <CardContent className="px-5 py-4">
              <div className="grid grid-cols-2 gap-x-6 gap-y-3">
                {data.contacts.length > 0 && (
                  <div>
                    <dt className="text-xs text-muted-foreground font-medium mb-1">
                      Contacts
                    </dt>
                    <dd className="space-y-0.5">
                      {visibleContacts.map((c, i) => (
                        <div key={i} className="text-sm text-foreground">
                          {c}
                        </div>
                      ))}
                    </dd>
                    <ShowMore
                      total={data.contacts.length}
                      expanded={contactsExpanded}
                      onToggle={() => setContactsExpanded(!contactsExpanded)}
                    />
                  </div>
                )}
                {data.phones.length > 0 && (
                  <div>
                    <dt className="text-xs text-muted-foreground font-medium mb-1">
                      Phones
                    </dt>
                    <dd className="space-y-0.5">
                      {visiblePhones.map((p, i) => (
                        <div key={i} className="text-sm text-foreground">
                          {p}
                        </div>
                      ))}
                    </dd>
                    <ShowMore
                      total={data.phones.length}
                      expanded={phonesExpanded}
                      onToggle={() => setPhonesExpanded(!phonesExpanded)}
                    />
                  </div>
                )}
                {data.addresses.length > 0 && (
                  <div className="col-span-2">
                    <dt className="text-xs text-muted-foreground font-medium mb-1">
                      Addresses
                    </dt>
                    <dd className="space-y-0.5">
                      {visibleAddresses.map((a, i) => (
                        <div key={i} className="text-sm text-foreground">
                          {a}
                        </div>
                      ))}
                    </dd>
                    <ShowMore
                      total={data.addresses.length}
                      expanded={addressesExpanded}
                      onToggle={() => setAddressesExpanded(!addressesExpanded)}
                    />
                  </div>
                )}
              </div>
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
                    {visibleTxns.map((app) => (
                      <tr
                        key={`${app.rt_id}-${app.role}`}
                        className="border-b border-border hover:bg-accent cursor-pointer transition-colors"
                        onClick={() => navigate(`/transactions/${app.rt_id}`)}
                      >
                        <td className="py-3 pr-4 text-xs font-mono text-primary">
                          {app.rt_id}
                        </td>
                        <td className="py-3 pr-4">
                          <RoleBadge role={app.role} />
                        </td>
                        <td className="py-3 pr-4 text-xs text-foreground">
                          {app.sale_date_iso}
                        </td>
                        <td className="py-3 pr-4 text-xs text-foreground">
                          {app.sale_price}
                        </td>
                        <td className="py-3 pr-4 text-xs text-foreground max-w-[200px] truncate">
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

        {/* Linked Properties */}
        {data.linked_properties.length > 0 && (
          <Card>
            <CardHeader className="px-5 py-3 border-b border-border">
              <CardTitle className="text-sm font-semibold uppercase tracking-wider">
                Linked Properties ({data.linked_properties.length})
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
                      Address
                    </th>
                    <th className="text-left text-[10px] font-medium text-muted-foreground uppercase py-2 pr-4">
                      City
                    </th>
                    <th className="text-left text-[10px] font-medium text-muted-foreground uppercase py-2">
                      Txns
                    </th>
                  </tr>
                </thead>
                <tbody>
                  {visibleProps.map((prop) => (
                    <tr
                      key={prop.prop_id}
                      className="border-b border-border hover:bg-accent cursor-pointer transition-colors"
                      onClick={() => navigate(`/properties/${prop.prop_id}`)}
                    >
                      <td className="py-3 pr-4 text-xs font-mono text-primary">
                        {prop.prop_id}
                      </td>
                      <td className="py-3 pr-4 text-xs text-foreground">
                        {prop.address}
                      </td>
                      <td className="py-3 pr-4 text-xs text-foreground">
                        {prop.city}
                      </td>
                      <td className="py-3 text-xs text-foreground">
                        {prop.transaction_count}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
              <ShowMore
                total={data.linked_properties.length}
                expanded={propsExpanded}
                onToggle={() => setPropsExpanded(!propsExpanded)}
              />
            </CardContent>
          </Card>
        )}

        <SuggestedAffiliates groupId={data.group_id} onMerge={reload} />

        <DataIssueCard entityId={data.group_id} />
      </div>

      {/* Name evidence drawer */}
      <Sheet open={drawerName !== null} onOpenChange={(open) => { if (!open) setDrawerName(null); }}>
        <SheetContent side="right" className="w-full max-w-2xl sm:max-w-2xl overflow-y-auto">
          <SheetHeader>
            <SheetTitle>{drawerName || ""}</SheetTitle>
            <SheetDescription>{data.group_id} — {data.display_name}</SheetDescription>
          </SheetHeader>
          {drawerName && (
            <NameEvidenceDrawer
              groupId={data.group_id}
              name={drawerName}
              appearances={data.appearances.filter((a) => {
                const normTarget = drawerName.toUpperCase().replace(/\s+/g, " ").trim();
                const normApp = a.name.toUpperCase().replace(/\s+/g, " ").trim();
                return normApp === normTarget;
              })}
              isConfirmed={data.confirmed_names.includes(
                drawerName.toUpperCase().replace(/\s+/g, " ").trim()
              )}
              saving={saving}
              onConfirm={() => confirmName(drawerName)}
              onDisconnect={async (targetGroup, reason) => {
                const result = await disconnectName(drawerName, targetGroup, reason);
                if (result) setDrawerName(null);
                return result;
              }}
              onClose={() => setDrawerName(null)}
            />
          )}
        </SheetContent>
      </Sheet>
    </div>
  );
}
