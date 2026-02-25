import { useMemo, useState } from "react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import type { OutreachFilters, FilterOptions } from "../../types/outreach";
import { DEFAULT_FILTERS } from "../../types/outreach";

interface Props {
  filterOptions: FilterOptions;
  initialFilters?: OutreachFilters;
  onPreview: (filters: OutreachFilters) => void;
  loading?: boolean;
}

export default function OutreachFilterForm({
  filterOptions,
  initialFilters,
  onPreview,
  loading,
}: Props) {
  const [filters, setFilters] = useState<OutreachFilters>(
    initialFilters || { ...DEFAULT_FILTERS },
  );

  const [citySearch, setCitySearch] = useState("");
  const [brandSearch, setBrandSearch] = useState("");

  const toggleCity = (city: string) => {
    setFilters((f) => ({
      ...f,
      cities: f.cities.includes(city)
        ? f.cities.filter((c) => c !== city)
        : [...f.cities, city],
    }));
  };

  const toggleBrand = (brand: string) => {
    setFilters((f) => ({
      ...f,
      brands: f.brands.includes(brand)
        ? f.brands.filter((b) => b !== brand)
        : [...f.brands, brand],
    }));
  };

  const toggleCategory = (cat: string) => {
    setFilters((f) => ({
      ...f,
      brand_categories: f.brand_categories.includes(cat)
        ? f.brand_categories.filter((c) => c !== cat)
        : [...f.brand_categories, cat],
    }));
  };

  // Build available categories with counts from matched brands
  const { availableCategories, categoryCounts } = useMemo(() => {
    const counts: Record<string, number> = {};
    const catSet = new Set<string>();
    for (const brand of filterOptions.brands) {
      const cat = filterOptions.brand_categories[brand];
      if (cat) {
        catSet.add(cat);
        counts[cat] = (counts[cat] || 0) + 1;
      }
    }
    const entries: [string, string][] = [];
    for (const cat of catSet) {
      const label = filterOptions.category_labels[cat] || cat;
      entries.push([cat, label]);
    }
    entries.sort((a, b) => a[1].localeCompare(b[1]));
    return { availableCategories: entries, categoryCounts: counts };
  }, [filterOptions]);

  const filteredCities = citySearch
    ? filterOptions.cities.filter((c) =>
        c.toLowerCase().includes(citySearch.toLowerCase()),
      )
    : filterOptions.cities;

  const filteredBrands = brandSearch
    ? filterOptions.brands.filter((b) =>
        b.toLowerCase().includes(brandSearch.toLowerCase()),
      )
    : filterOptions.brands;

  return (
    <div className="space-y-5">
      {/* Cities */}
      <div>
        <label className="text-xs font-medium text-muted-foreground uppercase tracking-wider">
          Cities
        </label>
        <Input
          placeholder="Search cities..."
          value={citySearch}
          onChange={(e) => setCitySearch(e.target.value)}
          className="mt-1 h-8 text-sm"
        />
        <div className="mt-2 max-h-36 overflow-y-auto border border-border rounded-md p-2 space-y-0.5">
          {filteredCities.slice(0, 200).map((city) => (
            <label
              key={city}
              className="flex items-center gap-2 text-sm cursor-pointer hover:bg-accent px-1.5 py-0.5 rounded"
            >
              <input
                type="checkbox"
                checked={filters.cities.includes(city)}
                onChange={() => toggleCity(city)}
                className="rounded border-input"
              />
              {city}
            </label>
          ))}
          {filteredCities.length === 0 && (
            <div className="text-xs text-muted-foreground py-1">No cities match</div>
          )}
        </div>
        {filters.cities.length > 0 && (
          <div className="mt-1 text-xs text-muted-foreground">
            {filters.cities.length} selected
            <button
              className="ml-2 text-primary hover:underline"
              onClick={() => setFilters((f) => ({ ...f, cities: [] }))}
            >
              Clear
            </button>
          </div>
        )}
      </div>

      {/* Brand Categories */}
      <div>
        <label className="text-xs font-medium text-muted-foreground uppercase tracking-wider">
          Brand Category
        </label>
        <div className="mt-2 border border-border rounded-md p-2 space-y-0.5">
          {availableCategories.map(([cat, label]) => (
            <label
              key={cat}
              className="flex items-center gap-2 text-sm cursor-pointer hover:bg-accent px-1.5 py-0.5 rounded"
            >
              <input
                type="checkbox"
                checked={filters.brand_categories.includes(cat)}
                onChange={() => toggleCategory(cat)}
                className="rounded border-input"
              />
              {label}
              <span className="text-xs text-muted-foreground ml-auto">
                {categoryCounts[cat] || 0}
              </span>
            </label>
          ))}
        </div>
        {filters.brand_categories.length > 0 && (
          <div className="mt-1 text-xs text-muted-foreground">
            {filters.brand_categories.length} selected
            <button
              className="ml-2 text-primary hover:underline"
              onClick={() =>
                setFilters((f) => ({ ...f, brand_categories: [] }))
              }
            >
              Clear
            </button>
          </div>
        )}
      </div>

      {/* Individual Brands */}
      <div>
        <label className="text-xs font-medium text-muted-foreground uppercase tracking-wider">
          Specific Brands
        </label>
        <Input
          placeholder="Search brands..."
          value={brandSearch}
          onChange={(e) => setBrandSearch(e.target.value)}
          className="mt-1 h-8 text-sm"
        />
        <div className="mt-2 max-h-36 overflow-y-auto border border-border rounded-md p-2 space-y-0.5">
          {filteredBrands.slice(0, 200).map((brand) => (
            <label
              key={brand}
              className="flex items-center gap-2 text-sm cursor-pointer hover:bg-accent px-1.5 py-0.5 rounded"
            >
              <input
                type="checkbox"
                checked={filters.brands.includes(brand)}
                onChange={() => toggleBrand(brand)}
                className="rounded border-input"
              />
              {brand}
              {filterOptions.brand_categories[brand] && (
                <span className="text-[10px] text-muted-foreground ml-auto">
                  {filterOptions.category_labels[filterOptions.brand_categories[brand]] ||
                    filterOptions.brand_categories[brand]}
                </span>
              )}
            </label>
          ))}
          {filteredBrands.length === 0 && (
            <div className="text-xs text-muted-foreground py-1">No brands match</div>
          )}
        </div>
        {filters.brands.length > 0 && (
          <div className="mt-1 text-xs text-muted-foreground">
            {filters.brands.length} selected
            <button
              className="ml-2 text-primary hover:underline"
              onClick={() => setFilters((f) => ({ ...f, brands: [] }))}
            >
              Clear
            </button>
          </div>
        )}
      </div>

      {/* Date range */}
      <div className="grid grid-cols-2 gap-3">
        <div>
          <label className="text-xs font-medium text-muted-foreground uppercase tracking-wider">
            Sale Date From
          </label>
          <Input
            type="date"
            value={filters.sale_date_from}
            onChange={(e) =>
              setFilters((f) => ({ ...f, sale_date_from: e.target.value }))
            }
            className="mt-1 h-8 text-sm"
          />
        </div>
        <div>
          <label className="text-xs font-medium text-muted-foreground uppercase tracking-wider">
            Sale Date To
          </label>
          <Input
            type="date"
            value={filters.sale_date_to}
            onChange={(e) =>
              setFilters((f) => ({ ...f, sale_date_to: e.target.value }))
            }
            className="mt-1 h-8 text-sm"
          />
        </div>
      </div>

      {/* Price range */}
      <div className="grid grid-cols-2 gap-3">
        <div>
          <label className="text-xs font-medium text-muted-foreground uppercase tracking-wider">
            Price Min
          </label>
          <Input
            type="number"
            placeholder="e.g. 500000"
            value={filters.price_min ?? ""}
            onChange={(e) =>
              setFilters((f) => ({
                ...f,
                price_min: e.target.value ? Number(e.target.value) : null,
              }))
            }
            className="mt-1 h-8 text-sm"
          />
        </div>
        <div>
          <label className="text-xs font-medium text-muted-foreground uppercase tracking-wider">
            Price Max
          </label>
          <Input
            type="number"
            placeholder="e.g. 5000000"
            value={filters.price_max ?? ""}
            onChange={(e) =>
              setFilters((f) => ({
                ...f,
                price_max: e.target.value ? Number(e.target.value) : null,
              }))
            }
            className="mt-1 h-8 text-sm"
          />
        </div>
      </div>

      {/* Owner type */}
      <div>
        <label className="text-xs font-medium text-muted-foreground uppercase tracking-wider">
          Owner Type
        </label>
        <select
          value={filters.owner_type || ""}
          onChange={(e) =>
            setFilters((f) => ({ ...f, owner_type: e.target.value || null }))
          }
          className="mt-1 h-8 w-full rounded-md border border-input bg-background px-3 text-sm"
        >
          <option value="">Any</option>
          <option value="company">Company</option>
          <option value="person">Person</option>
        </select>
      </div>

      {/* Exclude toggles */}
      <div className="space-y-2">
        <label className="flex items-center gap-2 text-sm cursor-pointer">
          <input
            type="checkbox"
            checked={filters.exclude_contacted}
            onChange={(e) =>
              setFilters((f) => ({ ...f, exclude_contacted: e.target.checked }))
            }
            className="rounded border-input"
          />
          Exclude previously contacted properties
        </label>
        <label className="flex items-center gap-2 text-sm cursor-pointer">
          <input
            type="checkbox"
            checked={filters.exclude_by_owner}
            onChange={(e) =>
              setFilters((f) => ({ ...f, exclude_by_owner: e.target.checked }))
            }
            className="rounded border-input"
          />
          Exclude by owner (any property with same owner contacted)
        </label>
      </div>

      {/* Actions */}
      <div className="flex gap-2">
        <Button onClick={() => onPreview(filters)} disabled={loading}>
          {loading ? "Loading..." : "Preview Results"}
        </Button>
        <Button
          variant="outline"
          onClick={() => {
            setFilters({ ...DEFAULT_FILTERS });
            setCitySearch("");
            setBrandSearch("");
          }}
        >
          Reset Filters
        </Button>
      </div>
    </div>
  );
}
