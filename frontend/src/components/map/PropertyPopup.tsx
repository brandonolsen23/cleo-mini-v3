import { useState } from "react";
import { Link } from "react-router-dom";
import type { PropertySummary } from "../../types/property";
import { usePropertyOutreach, logContact } from "../../api/outreach";
import {
  CONTACT_METHODS,
  METHOD_LABELS,
  type ContactMethod,
  OUTCOMES,
  OUTCOME_LABELS,
  type OutcomeType,
} from "../../types/outreach";
import PipelineStatusBadge from "../outreach/PipelineStatusBadge";
import BrandBadge from "../shared/BrandBadge";
import MapLink from "../shared/MapLink";
import { Button } from "@/components/ui/button";

interface Props {
  property: PropertySummary;
  onClose: () => void;
}

export default function PropertyPopup({ property, onClose }: Props) {
  const { data: outreach, loading: outreachLoading, reload } = usePropertyOutreach(property.prop_id);

  const [showLogForm, setShowLogForm] = useState(false);
  const [logMethod, setLogMethod] = useState<ContactMethod>("mail");
  const [logOutcome, setLogOutcome] = useState<OutcomeType | "">("");
  const [saving, setSaving] = useState(false);

  const handleQuickLog = async () => {
    setSaving(true);
    try {
      await logContact({
        prop_id: property.prop_id,
        method: logMethod,
        outcome: logOutcome || undefined,
        date: new Date().toISOString().slice(0, 10),
      });
      setShowLogForm(false);
      setLogOutcome("");
      reload();
    } finally {
      setSaving(false);
    }
  };

  return (
    <div className="min-w-[220px] max-w-[280px]">
      {property.primary_photo && (
        <img
          src={property.primary_photo}
          alt={property.address}
          className="w-full h-32 object-cover rounded-md mb-2"
        />
      )}
      <div className="flex items-start justify-between gap-2 mb-1">
        <h3 className="text-sm font-semibold text-foreground leading-tight flex items-center gap-1.5">
          {property.address}
          <MapLink
            address={`${property.address}, ${property.city}`}
            lat={property.lat}
            lng={property.lng}
          />
        </h3>
        <button
          onClick={onClose}
          className="text-muted-foreground hover:text-foreground text-lg leading-none -mt-0.5"
        >
          &times;
        </button>
      </div>
      <p className="text-xs text-muted-foreground mb-2">{property.city}</p>

      <div className="space-y-1 text-xs text-foreground">
        <div className="flex justify-between">
          <span>Transactions</span>
          <span className="font-medium">{property.transaction_count}</span>
        </div>
        {property.latest_sale_price && (
          <div className="flex justify-between">
            <span>Latest price</span>
            <span className="font-medium">{property.latest_sale_price}</span>
          </div>
        )}
        {property.latest_sale_year && (
          <div className="flex justify-between">
            <span>Latest sale</span>
            <span className="font-medium">{property.latest_sale_year}</span>
          </div>
        )}
        {property.brands.length > 0 && (
          <div className="flex flex-wrap gap-1 pt-1">
            {property.brands.map((b) => (
              <BrandBadge key={b} brand={b} />
            ))}
          </div>
        )}
      </div>

      {/* Pipeline / deal status */}
      <div className="flex items-center justify-between mt-2 pt-2 border-t border-border">
        <PipelineStatusBadge status={property.pin_status ?? property.pipeline_status ?? "not_started"} />
        {!outreachLoading && outreach && outreach.entries.length > 0 && (
          <span className="text-[10px] text-muted-foreground">
            {outreach.entries.length} touchpoint{outreach.entries.length !== 1 ? "s" : ""}
          </span>
        )}
      </div>

      {/* Quick log form */}
      {showLogForm && (
        <div className="mt-2 pt-2 border-t border-border space-y-1.5">
          <div className="flex gap-1">
            <select
              value={logMethod}
              onChange={(e) => setLogMethod(e.target.value as ContactMethod)}
              className="h-7 flex-1 rounded border border-input bg-background px-1 text-xs"
            >
              {CONTACT_METHODS.map((m) => (
                <option key={m} value={m}>{METHOD_LABELS[m]}</option>
              ))}
            </select>
            <select
              value={logOutcome}
              onChange={(e) => setLogOutcome(e.target.value as OutcomeType | "")}
              className="h-7 flex-1 rounded border border-input bg-background px-1 text-xs"
            >
              <option value="">Outcome</option>
              {OUTCOMES.map((o) => (
                <option key={o} value={o}>{OUTCOME_LABELS[o]}</option>
              ))}
            </select>
          </div>
          <div className="flex gap-1">
            <Button size="sm" className="h-7 text-xs flex-1" onClick={handleQuickLog} disabled={saving}>
              {saving ? "..." : "Save"}
            </Button>
            <Button size="sm" variant="ghost" className="h-7 text-xs" onClick={() => setShowLogForm(false)}>
              Cancel
            </Button>
          </div>
        </div>
      )}

      <div className="flex gap-2 mt-3">
        <Button asChild variant="secondary" size="sm" className="flex-1 text-xs">
          <Link to={`/properties/${property.prop_id}`}>View details</Link>
        </Button>
        {!showLogForm && (
          <Button
            variant="outline"
            size="sm"
            className="text-xs"
            onClick={() => setShowLogForm(true)}
          >
            Log Contact
          </Button>
        )}
      </div>
    </div>
  );
}
