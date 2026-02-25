import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { X } from "@phosphor-icons/react";
import { useFilterOptions, previewOutreach, createOutreachList } from "../../api/outreach";
import type { OutreachFilters, OutreachItem } from "../../types/outreach";
import OutreachFilterForm from "./OutreachFilterForm";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Card, CardHeader, CardTitle, CardContent } from "@/components/ui/card";

export default function OutreachBuilderPage() {
  const { data: filterOptions, loading: optionsLoading } = useFilterOptions();
  const navigate = useNavigate();

  const [previewing, setPreviewing] = useState(false);
  const [previewItems, setPreviewItems] = useState<OutreachItem[] | null>(null);
  const [selectedIds, setSelectedIds] = useState<Set<string>>(new Set());
  const [lastFilters, setLastFilters] = useState<OutreachFilters | null>(null);

  // Save form
  const [showSave, setShowSave] = useState(false);
  const [listName, setListName] = useState("");
  const [listDesc, setListDesc] = useState("");
  const [saving, setSaving] = useState(false);

  const handlePreview = async (filters: OutreachFilters) => {
    setPreviewing(true);
    setPreviewItems(null);
    try {
      const result = await previewOutreach(filters);
      setPreviewItems(result.items);
      setSelectedIds(new Set(result.items.map((i) => i.prop_id)));
      setLastFilters(filters);
    } catch {
      // ignore
    } finally {
      setPreviewing(false);
    }
  };

  const toggleItem = (propId: string) => {
    setSelectedIds((prev) => {
      const next = new Set(prev);
      if (next.has(propId)) next.delete(propId);
      else next.add(propId);
      return next;
    });
  };

  const handleSave = async () => {
    if (!listName.trim() || !lastFilters || !previewItems) return;
    setSaving(true);
    try {
      const result = await createOutreachList({
        name: listName.trim(),
        description: listDesc.trim(),
        filters: lastFilters,
        prop_ids: previewItems
          .filter((i) => selectedIds.has(i.prop_id))
          .map((i) => i.prop_id),
      });
      navigate(`/outreach/${result.list_id}`);
    } catch {
      // ignore
    } finally {
      setSaving(false);
    }
  };

  if (optionsLoading) {
    return (
      <div className="flex items-center justify-center h-screen">
        <div className="text-muted-foreground">Loading filter options...</div>
      </div>
    );
  }

  return (
    <div className="flex flex-col h-screen">
      {/* Header */}
      <div className="flex-none px-6 py-4 bg-background border-b border-border">
        <div className="flex items-center justify-between">
          <div>
            <h1 className="text-lg font-semibold text-foreground">Build Outreach List</h1>
            <p className="text-sm text-muted-foreground mt-0.5">
              Filter properties, preview results, then save as a mailing list
            </p>
          </div>
          <Button variant="outline" onClick={() => navigate("/outreach")}>
            Back to Lists
          </Button>
        </div>
      </div>

      {/* Body */}
      <div className="flex-1 overflow-auto">
        <div className="flex gap-6 p-6">
          {/* Filters sidebar */}
          <div className="w-80 flex-none">
            <Card>
              <CardHeader className="border-b border-border">
                <CardTitle>Filters</CardTitle>
              </CardHeader>
              <CardContent className="pt-4">
                <OutreachFilterForm
                  filterOptions={filterOptions}
                  onPreview={handlePreview}
                  loading={previewing}
                />
              </CardContent>
            </Card>
          </div>

          {/* Results */}
          <div className="flex-1 min-w-0">
            {previewing && (
              <div className="flex items-center justify-center py-20">
                <div className="text-muted-foreground">Running preview...</div>
              </div>
            )}

            {previewItems && !previewing && (
              <>
                <div className="flex items-center justify-between mb-4">
                  <div className="text-sm text-muted-foreground">
                    {previewItems.length.toLocaleString()} properties found,{" "}
                    {selectedIds.size.toLocaleString()} selected
                  </div>
                  <div className="flex gap-2">
                    <Button
                      variant="outline"
                      size="sm"
                      onClick={() =>
                        setSelectedIds(new Set(previewItems.map((i) => i.prop_id)))
                      }
                    >
                      Select All
                    </Button>
                    <Button
                      variant="outline"
                      size="sm"
                      onClick={() => setSelectedIds(new Set())}
                    >
                      Deselect All
                    </Button>
                    <Button
                      size="sm"
                      onClick={() => setShowSave(true)}
                      disabled={selectedIds.size === 0}
                    >
                      Save List ({selectedIds.size})
                    </Button>
                  </div>
                </div>

                {/* Save dialog */}
                {showSave && (
                  <Card className="mb-4">
                    <CardContent className="pt-4">
                      <div className="space-y-3">
                        <div>
                          <label className="text-xs font-medium text-muted-foreground uppercase tracking-wider">
                            List Name
                          </label>
                          <Input
                            value={listName}
                            onChange={(e) => setListName(e.target.value)}
                            placeholder="e.g. Toronto Retail Owners Q1 2026"
                            className="mt-1 h-8 text-sm"
                          />
                        </div>
                        <div>
                          <label className="text-xs font-medium text-muted-foreground uppercase tracking-wider">
                            Description (optional)
                          </label>
                          <Input
                            value={listDesc}
                            onChange={(e) => setListDesc(e.target.value)}
                            placeholder="Notes about this list..."
                            className="mt-1 h-8 text-sm"
                          />
                        </div>
                        <div className="flex gap-2">
                          <Button
                            size="sm"
                            onClick={handleSave}
                            disabled={!listName.trim() || saving}
                          >
                            {saving ? "Saving..." : "Save"}
                          </Button>
                          <Button
                            size="sm"
                            variant="outline"
                            onClick={() => setShowSave(false)}
                          >
                            Cancel
                          </Button>
                        </div>
                      </div>
                    </CardContent>
                  </Card>
                )}

                {/* Results table */}
                <div className="border border-border rounded-lg overflow-hidden">
                  <table className="w-full">
                    <thead className="bg-muted">
                      <tr>
                        <th className="w-10 px-3 py-2.5">
                          <input
                            type="checkbox"
                            checked={
                              selectedIds.size === previewItems.length &&
                              previewItems.length > 0
                            }
                            onChange={() => {
                              if (selectedIds.size === previewItems.length) {
                                setSelectedIds(new Set());
                              } else {
                                setSelectedIds(
                                  new Set(previewItems.map((i) => i.prop_id)),
                                );
                              }
                            }}
                            className="rounded border-input"
                          />
                        </th>
                        <th className="text-left text-[10px] font-medium text-muted-foreground uppercase tracking-wider px-3 py-2.5">
                          Property
                        </th>
                        <th className="text-left text-[10px] font-medium text-muted-foreground uppercase tracking-wider px-3 py-2.5">
                          Owner
                        </th>
                        <th className="text-left text-[10px] font-medium text-muted-foreground uppercase tracking-wider px-3 py-2.5">
                          Corporate Address
                        </th>
                        <th className="text-left text-[10px] font-medium text-muted-foreground uppercase tracking-wider px-3 py-2.5">
                          Contact
                        </th>
                        <th className="text-left text-[10px] font-medium text-muted-foreground uppercase tracking-wider px-3 py-2.5">
                          Last Sale
                        </th>
                        <th className="w-10 px-3 py-2.5" />
                      </tr>
                    </thead>
                    <tbody>
                      {previewItems.map((item) => (
                        <tr
                          key={item.prop_id}
                          className={`border-b border-border transition-colors ${
                            selectedIds.has(item.prop_id)
                              ? "bg-background"
                              : "bg-muted/30 opacity-60"
                          }`}
                        >
                          <td className="px-3 py-2.5">
                            <input
                              type="checkbox"
                              checked={selectedIds.has(item.prop_id)}
                              onChange={() => toggleItem(item.prop_id)}
                              className="rounded border-input"
                            />
                          </td>
                          <td className="px-3 py-2.5">
                            <div className="text-sm font-medium">{item.address}</div>
                            <div className="text-xs text-muted-foreground">
                              {item.city}
                              {item.brands.length > 0 && (
                                <span className="ml-1">
                                  ({item.brands.join(", ")})
                                </span>
                              )}
                            </div>
                          </td>
                          <td className="px-3 py-2.5">
                            <div className="text-sm">{item.owner || "\u2014"}</div>
                            <div className="text-xs text-muted-foreground">
                              {item.owner_type || ""}
                            </div>
                          </td>
                          <td className="px-3 py-2.5">
                            <div className="text-sm truncate max-w-[200px]">
                              {item.corporate_address || "\u2014"}
                            </div>
                          </td>
                          <td className="px-3 py-2.5">
                            <div className="text-sm">
                              {item.contact_names.length > 0
                                ? item.contact_names.join(", ")
                                : "\u2014"}
                            </div>
                            {item.phones.length > 0 && (
                              <div className="text-xs text-muted-foreground">
                                {item.phones.join(", ")}
                              </div>
                            )}
                          </td>
                          <td className="px-3 py-2.5">
                            <div className="text-sm">
                              {item.latest_sale_date || "\u2014"}
                            </div>
                            <div className="text-xs text-muted-foreground">
                              {item.latest_sale_price || ""}
                            </div>
                          </td>
                          <td className="px-3 py-2.5">
                            {selectedIds.has(item.prop_id) && (
                              <button
                                onClick={() => toggleItem(item.prop_id)}
                                className="text-muted-foreground hover:text-destructive"
                                title="Remove from list"
                              >
                                <X size={14} />
                              </button>
                            )}
                          </td>
                        </tr>
                      ))}
                      {previewItems.length === 0 && (
                        <tr>
                          <td
                            colSpan={7}
                            className="px-4 py-12 text-center text-sm text-muted-foreground"
                          >
                            No properties match the current filters.
                          </td>
                        </tr>
                      )}
                    </tbody>
                  </table>
                </div>
              </>
            )}

            {!previewItems && !previewing && (
              <div className="flex items-center justify-center py-20 text-muted-foreground">
                Set filters and click "Preview Results" to see matching properties
              </div>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}
