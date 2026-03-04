import { CaretRight } from "@phosphor-icons/react";

interface MiniListItem {
  icon?: React.ReactNode;
  label: string;
  value: string | number;
  barPercent?: number;
}

interface MiniListProps {
  title: string;
  items: MiniListItem[];
  onItemClick?: (item: MiniListItem) => void;
}

export function MiniList({ title, items, onItemClick }: MiniListProps) {
  return (
    <div className="overflow-hidden rounded-[var(--card-radius)] border border-[var(--gray-6)]">
      <div className="border-b border-[var(--gray-6)] px-4 py-3">
        <span className="text-[14px] font-bold leading-[20px] text-[var(--gray-12)]">
          {title}
        </span>
      </div>
      <div>
        {items.map((item, i) => (
          <div
            key={i}
            className={`flex items-center gap-3 px-4 py-2.5 ${
              onItemClick
                ? "cursor-pointer hover:bg-[var(--gray-2)]"
                : ""
            } ${i < items.length - 1 ? "border-b border-[var(--gray-4)]" : ""}`}
            onClick={() => onItemClick?.(item)}
          >
            {item.icon && (
              <span className="shrink-0 text-[var(--gray-9)]">
                {item.icon}
              </span>
            )}
            <span className="flex-1 truncate text-[14px] leading-[20px] text-[var(--gray-12)]">
              {item.label}
            </span>
            <span className="shrink-0 text-[12px] leading-[16px] text-[var(--gray-9)]">
              {typeof item.value === "number" ? `${item.value}%` : item.value}
            </span>
            {item.barPercent !== undefined && (
              <div className="h-2 w-16 shrink-0 overflow-hidden rounded-full bg-[var(--gray-4)]">
                <div
                  className="h-full rounded-full bg-[var(--accent-9)]"
                  style={{ width: `${Math.min(100, item.barPercent)}%` }}
                />
              </div>
            )}
            {onItemClick && (
              <CaretRight
                size={13}
                className="shrink-0 text-[var(--gray-8)]"
              />
            )}
          </div>
        ))}
      </div>
    </div>
  );
}
