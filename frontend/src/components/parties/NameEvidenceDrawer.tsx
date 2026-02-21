import { useState, useEffect, useRef } from "react";
import { Check, LinkBreak, CaretDown, CaretUp, CheckCircle, Link } from "@phosphor-icons/react";
import { useTransactionDetails, useKnownAttributes, useGroupingReason } from "../../api/parties";
import type { KnownAttributes, GroupingReason } from "../../api/parties";
import type { PartyAppearance } from "../../types/party";
import { Button } from "@/components/ui/button";
import { cn } from "@/lib/utils";

const INITIAL_LIMIT = 10;

interface NameEvidenceDrawerProps {
  groupId: string;
  name: string;
  appearances: PartyAppearance[];
  isConfirmed: boolean;
  saving: boolean;
  onConfirm: () => void;
  onDisconnect: (targetGroup: string, reason: string) => Promise<any>;
  onClose: () => void;
}

function formatPrice(price: string): string {
  if (!price) return "";
  return price;
}

function norm(s: string): string {
  return s.toUpperCase().replace(/\s+/g, " ").trim();
}

function KnownTag({ names }: { names: string[] }) {
  return (
    <>
      {names.map((n) => (
        <span
          key={n}
          className="inline-flex items-center px-1.5 py-0 rounded text-[10px] font-semibold bg-sky-100 text-sky-700 ml-1"
        >
          {n}
        </span>
      ))}
    </>
  );
}

function PartyFields({
  label,
  data,
  highlight,
  known,
}: {
  label: string;
  data: any;
  highlight: boolean;
  known: KnownAttributes;
}) {
  if (!data || typeof data !== "object") return null;

  const name = data.name || "";
  const contact = data.contact || "";
  const phone = data.phone || "";
  const address = data.address || "";
  const alternateNames = data.alternate_names || [];
  const aliases = data.aliases || [];
  const attention = data.attention || "";

  // Hide attention when it duplicates contact
  const showAttention =
    attention && attention.toUpperCase() !== contact.toUpperCase();

  // Look up known-attribute tags
  const contactKnown = contact ? (known.contacts[norm(contact)] || []) : [];
  const phoneKnown = phone ? (known.phones[phone.trim()] || []) : [];
  const addressKnown = address ? (known.addresses[norm(address)] || []) : [];

  return (
    <div
      className={cn(
        "rounded-lg p-3 text-sm",
        highlight
          ? "border-l-4 border-primary bg-accent/50 pl-3"
          : "bg-muted pl-4"
      )}
    >
      <div className="text-xs font-medium text-muted-foreground uppercase mb-1.5">
        {label}
      </div>
      <div className="font-medium text-foreground">{name || "N/A"}</div>
      {/* Aliases -- primary evidence signal, shown prominently */}
      {aliases.length > 0 && (
        <div className="flex flex-wrap gap-1 mt-1">
          {aliases.map((a: string, i: number) => (
            <span
              key={i}
              className="inline-flex items-center px-2 py-0.5 rounded text-xs font-semibold bg-amber-100 text-amber-800"
            >
              {a}
            </span>
          ))}
        </div>
      )}
      {alternateNames.length > 0 && (
        <div className="flex flex-wrap gap-1 mt-1">
          {alternateNames.map((a: string, i: number) => (
            <span
              key={i}
              className="inline-flex items-center px-2 py-0.5 rounded text-xs font-medium bg-purple-100 text-purple-700"
            >
              {a}
            </span>
          ))}
        </div>
      )}
      {contact && (
        <div className="text-muted-foreground mt-1">
          <span className="text-muted-foreground text-xs">Contact:</span> {contact}
          {contactKnown.length > 0 && <KnownTag names={contactKnown} />}
        </div>
      )}
      {showAttention && (
        <div className="text-muted-foreground mt-0.5">
          <span className="text-muted-foreground text-xs">Attn:</span> {attention}
        </div>
      )}
      {phone && (
        <div className="text-muted-foreground mt-0.5">
          <span className="text-muted-foreground text-xs">Phone:</span> {phone}
          {phoneKnown.length > 0 && <KnownTag names={phoneKnown} />}
        </div>
      )}
      {address && (
        <div className="text-muted-foreground mt-0.5">
          <span className="text-muted-foreground text-xs">Address:</span> {address}
          {addressKnown.length > 0 && <KnownTag names={addressKnown} />}
        </div>
      )}
    </div>
  );
}

function matchesName(partyData: any, targetName: string): boolean {
  if (!partyData || typeof partyData !== "object") return false;
  const norm = targetName.toUpperCase().replace(/\s+/g, " ").trim();
  const partyName = (partyData.name || "").toUpperCase().replace(/\s+/g, " ").trim();
  if (partyName === norm) return true;
  // Check alternate_names and aliases
  for (const alt of partyData.alternate_names || []) {
    if (alt.toUpperCase().replace(/\s+/g, " ").trim() === norm) return true;
  }
  for (const alias of partyData.aliases || []) {
    if (alias.toUpperCase().replace(/\s+/g, " ").trim() === norm) return true;
  }
  return false;
}

function GroupingReasons({ reasons }: { reasons: GroupingReason[] }) {
  if (reasons.length === 0) return null;

  const typeStyles: Record<string, { bg: string; icon: string }> = {
    phone: { bg: "bg-blue-50 border-blue-200 text-blue-800", icon: "Phone" },
    contact: { bg: "bg-orange-50 border-orange-200 text-orange-800", icon: "Contact" },
    alias: { bg: "bg-amber-50 border-amber-200 text-amber-800", icon: "Alias" },
  };

  return (
    <div className="rounded-lg border border-border bg-muted/50 p-3">
      <div className="flex items-center gap-1.5 text-xs font-medium text-muted-foreground uppercase mb-2">
        <Link size={12} />
        Why this name is in this group
      </div>
      <div className="space-y-1.5">
        {reasons.map((r, i) => {
          const style = typeStyles[r.type] || typeStyles.contact;
          return (
            <div
              key={i}
              className={`flex items-start gap-2 rounded px-2.5 py-1.5 text-xs border ${style.bg}`}
            >
              <span className="font-semibold flex-none uppercase">{r.type}</span>
              <div>
                <span className="font-medium">{r.value}</span>
                {r.detail && (
                  <span className="text-muted-foreground ml-1">— {r.detail}</span>
                )}
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
}

export default function NameEvidenceDrawer({
  groupId,
  name,
  appearances,
  isConfirmed,
  saving,
  onConfirm,
  onDisconnect,
  onClose,
}: NameEvidenceDrawerProps) {
  const [showAll, setShowAll] = useState(false);
  const [disconnecting, setDisconnecting] = useState(false);
  const [targetGroup, setTargetGroup] = useState("");
  const [reason, setReason] = useState("");
  const disconnectRef = useRef<HTMLInputElement>(null);

  const known = useKnownAttributes();
  const { reasons: groupingReasons } = useGroupingReason(groupId, name);

  const visibleAppearances = showAll
    ? appearances
    : appearances.slice(0, INITIAL_LIMIT);
  const rtIds = visibleAppearances.map((a) => a.rt_id);
  const { data: txnData, loading: txnLoading } = useTransactionDetails(rtIds);

  useEffect(() => {
    if (disconnecting) disconnectRef.current?.focus();
  }, [disconnecting]);

  const handleDisconnect = async () => {
    const result = await onDisconnect(targetGroup, reason);
    if (result) {
      setDisconnecting(false);
      setTargetGroup("");
      setReason("");
      onClose();
    }
  };

  return (
    <div className="space-y-4">
      {/* Header actions */}
      <div className="flex items-center justify-between">
        <div className="text-sm text-muted-foreground">
          {appearances.length} appearance{appearances.length !== 1 ? "s" : ""}
        </div>
        <div className="flex items-center gap-2">
          {isConfirmed ? (
            <span className="inline-flex items-center gap-1 text-xs text-green-600 font-medium">
              <CheckCircle size={14} /> Confirmed
            </span>
          ) : (
            <Button
              variant="outline"
              size="sm"
              onClick={onConfirm}
              disabled={saving}
              className="text-xs text-green-700 bg-green-50 border-green-200 hover:bg-green-100"
            >
              <Check size={13} /> Confirm
            </Button>
          )}
          <Button
            variant="outline"
            size="sm"
            onClick={() => setDisconnecting(!disconnecting)}
            disabled={saving}
            className="text-xs text-destructive bg-red-50 border-red-200 hover:bg-red-100"
          >
            <LinkBreak size={13} /> Disconnect
          </Button>
        </div>
      </div>

      {/* Grouping reason */}
      <GroupingReasons reasons={groupingReasons} />

      {/* Disconnect form */}
      {disconnecting && (
        <div className="p-3 bg-muted rounded-lg border border-border text-sm space-y-2">
          <div className="text-xs text-muted-foreground font-medium">
            Disconnect "{name}" from this group
          </div>
          <div className="flex items-center gap-2">
            <label className="text-xs text-muted-foreground w-24 flex-none">
              Move to group
            </label>
            <input
              ref={disconnectRef}
              type="text"
              value={targetGroup}
              onChange={(e) => setTargetGroup(e.target.value)}
              onKeyDown={(e) => {
                if (e.key === "Enter") handleDisconnect();
                if (e.key === "Escape") setDisconnecting(false);
              }}
              placeholder="G_____ (blank = new group)"
              className="flex-1 px-2 py-1 text-sm border border-border rounded bg-background focus:outline-none focus:ring-2 focus:ring-ring focus:border-transparent"
            />
          </div>
          <div className="flex items-center gap-2">
            <label className="text-xs text-muted-foreground w-24 flex-none">
              Reason
            </label>
            <input
              type="text"
              value={reason}
              onChange={(e) => setReason(e.target.value)}
              onKeyDown={(e) => {
                if (e.key === "Enter") handleDisconnect();
                if (e.key === "Escape") setDisconnecting(false);
              }}
              placeholder="e.g. Different parent company"
              className="flex-1 px-2 py-1 text-sm border border-border rounded bg-background focus:outline-none focus:ring-2 focus:ring-ring focus:border-transparent"
            />
          </div>
          <div className="flex items-center gap-2">
            <Button
              variant="destructive"
              size="sm"
              onClick={handleDisconnect}
              disabled={saving}
              className="text-xs"
            >
              {saving ? "Saving..." : "Disconnect"}
            </Button>
            <Button
              variant="outline"
              size="sm"
              onClick={() => setDisconnecting(false)}
              className="text-xs"
            >
              Cancel
            </Button>
          </div>
        </div>
      )}

      {/* Transaction evidence cards */}
      {txnLoading && visibleAppearances.some((a) => !(a.rt_id in txnData)) && (
        <div className="text-sm text-muted-foreground">Loading transaction details...</div>
      )}

      {visibleAppearances.map((app) => {
        const txn = txnData[app.rt_id];
        if (!txn) {
          return (
            <div
              key={`${app.rt_id}-${app.role}`}
              className="border border-border rounded-lg p-4"
            >
              <div className="flex items-center justify-between">
                <span className="font-mono text-sm text-primary">
                  {app.rt_id}
                </span>
                <span
                  className={cn(
                    "inline-flex items-center px-2 py-0.5 rounded text-xs font-medium",
                    app.role === "buyer"
                      ? "bg-green-100 text-green-700"
                      : "bg-orange-100 text-orange-700"
                  )}
                >
                  {app.role === "buyer" ? "Buyer" : "Seller"}
                </span>
              </div>
              <div className="text-sm text-muted-foreground mt-1">Loading...</div>
            </div>
          );
        }

        const tx = txn.transaction || {};
        const addr = tx.address || {};
        const seller = txn.transferor || {};
        const buyer = txn.transferee || {};

        const sellerHighlight = matchesName(seller, name);
        const buyerHighlight = matchesName(buyer, name);

        return (
          <div
            key={`${app.rt_id}-${app.role}`}
            className="border border-border rounded-lg overflow-hidden"
          >
            {/* Transaction header */}
            <div className="px-4 py-3 bg-muted border-b border-border flex items-center justify-between">
              <div className="flex items-center gap-3">
                <span className="font-mono text-sm text-primary">
                  {app.rt_id}
                </span>
                <span
                  className={cn(
                    "inline-flex items-center px-2 py-0.5 rounded text-xs font-medium",
                    app.role === "buyer"
                      ? "bg-green-100 text-green-700"
                      : "bg-orange-100 text-orange-700"
                  )}
                >
                  {app.role === "buyer" ? "Buyer" : "Seller"}
                </span>
              </div>
              <span className="text-xs text-muted-foreground">
                {app.sale_date_iso}
              </span>
            </div>

            <div className="p-4 space-y-3">
              {/* Property info */}
              <div className="text-sm">
                <div className="font-medium text-foreground">
                  {addr.address || app.prop_address || "N/A"}
                  {(addr.city || app.prop_city) && (
                    <span className="text-muted-foreground">
                      , {addr.city || app.prop_city}
                    </span>
                  )}
                </div>
                {tx.sale_price && (
                  <div className="text-muted-foreground mt-0.5">
                    {formatPrice(tx.sale_price)}
                  </div>
                )}
              </div>

              {/* Seller */}
              <PartyFields
                label="Seller"
                data={seller}
                highlight={sellerHighlight}
                known={known}
              />

              {/* Buyer */}
              <PartyFields
                label="Buyer"
                data={buyer}
                highlight={buyerHighlight}
                known={known}
              />
            </div>
          </div>
        );
      })}

      {/* Load more */}
      {appearances.length > INITIAL_LIMIT && (
        <Button
          variant="ghost"
          size="sm"
          onClick={() => setShowAll(!showAll)}
          className="h-auto px-0 py-0 text-xs font-medium text-muted-foreground hover:text-foreground hover:bg-transparent"
        >
          {showAll ? (
            <>
              <CaretUp size={14} /> Show less
            </>
          ) : (
            <>
              <CaretDown size={14} /> Show all{" "}
              {appearances.length.toLocaleString()}
            </>
          )}
        </Button>
      )}
    </div>
  );
}
