import { MagnifyingGlass, Plus, CalendarBlank } from "@phosphor-icons/react";
import { cn } from "@/lib/utils";

interface FilterOption {
  label: string;
  icon?: React.ReactNode;
  onClick: () => void;
  active?: boolean;
}

interface SearchToolbarProps {
  value: string;
  onChange: (value: string) => void;
  placeholder?: string;
  filters?: FilterOption[];
}

export function SearchToolbar({
  value,
  onChange,
  placeholder = "Search",
  filters,
}: SearchToolbarProps) {
  return (
    <div className="flex items-center gap-3">
      {/* Search input — WorkOS style: max-width ~400px, filters sit adjacent */}
      <div className="relative w-full max-w-[400px]">
        <MagnifyingGlass
          size={15}
          className="absolute left-3 top-1/2 -translate-y-1/2 text-[var(--gray-9)]"
        />
        <input
          type="text"
          value={value}
          onChange={(e) => onChange(e.target.value)}
          placeholder={placeholder}
          className="h-8 w-full rounded-[var(--radius-2)] border border-[var(--gray-7)] bg-white pl-9 pr-3 text-[14px] text-[var(--gray-12)] placeholder:text-[var(--gray-9)] focus:border-[var(--accent-8)] focus:outline-none"
        />
      </div>

      {/* Filter pill buttons — WorkOS style: border sand-30, rounded */}
      {filters?.map((filter) => (
        <button
          key={filter.label}
          onClick={filter.onClick}
          className={cn(
            "inline-flex h-8 items-center gap-1.5 rounded-[var(--radius-2)] border px-3 text-[13px] font-medium transition-colors",
            filter.active
              ? "border-[var(--accent-7)] bg-[var(--accent-a2)] text-[var(--accent-11)]"
              : "border-[var(--gray-7)] text-[var(--gray-11)] hover:bg-[var(--gray-2)]"
          )}
        >
          {filter.icon}
          {filter.label}
        </button>
      ))}
    </div>
  );
}

/** Pre-built filter icons matching WorkOS style */
export const FilterIcons = {
  add: <Plus size={13} weight="bold" />,
  calendar: <CalendarBlank size={13} />,
} as const;
