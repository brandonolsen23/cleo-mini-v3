import { useState, useRef, useEffect } from "react";
import { DotsThree, WarningCircle } from "@phosphor-icons/react";
import { Text } from "@radix-ui/themes";
import { mutateApi } from "@/api/client";

/* Human-readable labels for internal field names */
const FIELD_LABELS: Record<string, string> = {
  // Core four (seller side)
  seller_company_name: "Seller — Company Name",
  seller_contact_name: "Seller — Contact Name",
  seller_phone: "Seller — Phone",
  seller_corp_address: "Seller — Corp Address",
  // Core four (buyer side)
  buyer_company_name: "Buyer — Company Name",
  buyer_contact_name: "Buyer — Contact Name",
  buyer_phone: "Buyer — Phone",
  buyer_corp_address: "Buyer — Corp Address",
  // Transaction shared
  sale_price: "Sale Price",
  sale_date: "Sale Date",
  // Owner card (same four buckets)
  company_name: "Company Name",
  contact_name: "Contact Name",
  phone: "Phone",
  corp_address: "Corp Address",
  // Property-level fields
  primary_address: "Primary Address",
  city: "City",
  geocode_location: "Geocode / Map Location",
  parcel_assignment: "Parcel Assignment",
  missing_data: "Missing Data",
  duplicate_property: "Duplicate Property",
  // Parcel fields
  arn: "ARN",
  pin: "PIN",
  parcel_boundary: "Parcel Boundary",
  centroid: "Centroid",
  parcel_method: "Resolution Method",
  // Brand / OSM tenant fields
  tenant_name: "Tenant Name",
  tenant_brand: "Brand Name",
  tenant_address: "Address",
  tenant_category: "Category",
  tenant_phone: "Phone",
  tenant_website: "Website",
  tenant_location: "Location / Coordinates",
  tenant_wrong_property: "Wrong Property Match",
  // Entity-level fields
  entity_name: "Entity Name",
  entity_grouping: "Entity Grouping",
  missing_transactions: "Missing Transactions",
  duplicate_entity: "Duplicate Entity",
  wrong_link: "Wrong Link",
};

function fieldLabel(field: string): string {
  return FIELD_LABELS[field] || field;
}

/**
 * 3-dot menu that lets the user flag a data issue on a source record.
 *
 * Props:
 *   sourceId  — the RT/GW/BR/OSM ID or property/entity ID
 *   fields    — internal field names to offer in the dropdown
 *   page      — page context (e.g. "entity_detail", "property_detail")
 *   context   — extra context string (e.g. entity name or property address)
 */
export function FlagIssueMenu({
  sourceId,
  fields,
  page = "",
  context = "",
}: {
  sourceId: string;
  fields: string[];
  page?: string;
  context?: string;
}) {
  const [menuOpen, setMenuOpen] = useState(false);
  const [modalOpen, setModalOpen] = useState(false);
  const [field, setField] = useState(fields[0] || "");
  const [note, setNote] = useState("");
  const [saving, setSaving] = useState(false);
  const [saved, setSaved] = useState(false);
  const menuRef = useRef<HTMLDivElement>(null);

  // Close menu on outside click
  useEffect(() => {
    if (!menuOpen) return;
    const handler = (e: MouseEvent) => {
      if (menuRef.current && !menuRef.current.contains(e.target as Node)) {
        setMenuOpen(false);
      }
    };
    document.addEventListener("mousedown", handler);
    return () => document.removeEventListener("mousedown", handler);
  }, [menuOpen]);

  const handleSubmit = async () => {
    if (!field) return;
    setSaving(true);
    try {
      await mutateApi("/issues", "POST", {
        source_id: sourceId,
        field,
        note,
        page,
        context,
      });
      setSaved(true);
      setTimeout(() => {
        setModalOpen(false);
        setSaved(false);
        setNote("");
        setField(fields[0] || "");
      }, 800);
    } catch (e: any) {
      alert(`Failed to save issue: ${e?.message || e}`);
    } finally {
      setSaving(false);
    }
  };

  return (
    <>
      {/* 3-dot trigger */}
      <div ref={menuRef} className="relative">
        <button
          onClick={(e) => {
            e.stopPropagation();
            setMenuOpen((v) => !v);
          }}
          className="flex h-6 w-6 items-center justify-center rounded-[var(--radius-1)] text-[var(--gray-8)] hover:bg-[var(--gray-3)] hover:text-[var(--gray-11)]"
          title="Actions"
        >
          <DotsThree size={18} weight="bold" />
        </button>

        {menuOpen && (
          <div className="absolute right-0 top-full z-30 mt-1 min-w-[140px] rounded-[var(--radius-2)] border border-[var(--gray-6)] bg-white py-1 shadow-lg">
            <button
              onClick={(e) => {
                e.stopPropagation();
                setMenuOpen(false);
                setModalOpen(true);
              }}
              className="flex w-full items-center gap-2 px-3 py-1.5 text-left text-[13px] text-[var(--gray-11)] hover:bg-[var(--gray-3)]"
            >
              <WarningCircle size={14} className="text-[var(--amber-9)]" />
              Data Issue
            </button>
          </div>
        )}
      </div>

      {/* Modal */}
      {modalOpen && (
        <div
          className="fixed inset-0 z-50 flex items-center justify-center bg-black/30"
          onClick={() => setModalOpen(false)}
        >
          <div
            className="w-[380px] rounded-[var(--card-radius)] border border-[var(--gray-6)] bg-white p-5 shadow-[var(--elevation-4)]"
            onClick={(e) => e.stopPropagation()}
          >
            <div className="mb-4 flex items-center gap-2">
              <WarningCircle size={18} className="text-[var(--amber-9)]" />
              <Text size="3" weight="medium">
                Flag Data Issue
              </Text>
            </div>

            <div className="mb-2">
              <Text size="1" color="gray" className="block mb-1">
                Source ID
              </Text>
              <Text size="2" className="block font-mono text-[var(--gray-11)]">
                {sourceId}
              </Text>
            </div>

            <div className="mb-3">
              <label className="mb-1 block text-[12px] font-medium text-[var(--gray-11)]">
                Field
              </label>
              <select
                value={field}
                onChange={(e) => setField(e.target.value)}
                className="w-full rounded-[var(--radius-2)] border border-[var(--gray-6)] bg-white px-3 py-1.5 text-[13px] text-[var(--gray-12)] focus:border-[var(--accent-8)] focus:outline-none"
              >
                {fields.map((f) => (
                  <option key={f} value={f}>
                    {fieldLabel(f)}
                  </option>
                ))}
              </select>
            </div>

            <div className="mb-4">
              <label className="mb-1 block text-[12px] font-medium text-[var(--gray-11)]">
                Note
              </label>
              <textarea
                value={note}
                onChange={(e) => setNote(e.target.value)}
                placeholder="What's wrong with this field?"
                rows={3}
                className="w-full rounded-[var(--radius-2)] border border-[var(--gray-6)] px-3 py-2 text-[13px] text-[var(--gray-12)] placeholder:text-[var(--gray-8)] focus:border-[var(--accent-8)] focus:outline-none"
              />
            </div>

            <div className="flex justify-end gap-2">
              <button
                onClick={() => {
                  setModalOpen(false);
                  setNote("");
                  setField(fields[0] || "");
                }}
                className="rounded-[var(--radius-2)] border border-[var(--gray-6)] px-3 py-1.5 text-[13px] font-medium text-[var(--gray-11)] hover:bg-[var(--gray-3)]"
              >
                Cancel
              </button>
              <button
                onClick={handleSubmit}
                disabled={saving || !field}
                className="rounded-[var(--radius-2)] bg-[var(--amber-9)] px-3 py-1.5 text-[13px] font-medium text-white hover:bg-[var(--amber-10)] disabled:opacity-50"
              >
                {saved ? "Saved" : saving ? "Saving..." : "Flag Issue"}
              </button>
            </div>
          </div>
        </div>
      )}
    </>
  );
}
