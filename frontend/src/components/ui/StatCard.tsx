import { TrendUp, TrendDown } from "@phosphor-icons/react";
import { formatCompact, formatPercent } from "@/lib/utils";

interface StatCardProps {
  label: string;
  value: number | string;
  change?: number;
  dotColor?: string;
  format?: "number" | "currency" | "raw";
}

export function StatCard({
  label,
  value,
  change,
  dotColor,
  format = "number",
}: StatCardProps) {
  const displayValue =
    format === "number" && typeof value === "number"
      ? formatCompact(value)
      : value;

  return (
    <div className="flex flex-col gap-1">
      <div className="flex items-baseline gap-2">
        <span className="text-[28px] font-bold leading-[36px] tracking-[-0.4px] text-[var(--gray-12)]">
          {displayValue}
        </span>
        {change !== undefined && (
          <span
            className={`inline-flex items-center gap-0.5 text-[12px] font-medium leading-[16px] ${
              change >= 0 ? "text-[var(--green-11)]" : "text-[var(--red-11)]"
            }`}
          >
            {change >= 0 ? (
              <TrendUp size={12} weight="bold" />
            ) : (
              <TrendDown size={12} weight="bold" />
            )}
            {formatPercent(Math.abs(change))}
          </span>
        )}
      </div>
      <div className="flex items-center gap-1.5">
        {dotColor && (
          <span
            className="inline-block h-2 w-2 rounded-full"
            style={{ backgroundColor: dotColor }}
          />
        )}
        <span className="text-[12px] font-medium leading-[16px] text-[var(--gray-11)]">
          {label}
        </span>
      </div>
    </div>
  );
}
