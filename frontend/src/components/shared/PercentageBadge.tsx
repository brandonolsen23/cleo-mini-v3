import { ArrowUp, ArrowDown } from "@phosphor-icons/react";
import { cn } from "@/lib/utils";

interface PercentageBadgeProps {
  value: number;
  large?: boolean;
  className?: string;
}

export default function PercentageBadge({ value, large, className }: PercentageBadgeProps) {
  const positive = value >= 0;

  return (
    <span
      className={cn(
        "inline-flex items-center gap-0.5 rounded-lg border px-1.5 font-semibold",
        large ? "h-8 text-xs" : "h-7 text-[11px]",
        positive
          ? "border-green/30 bg-green-light text-green"
          : "border-red/30 bg-red-light text-red",
        className,
      )}
    >
      {positive ? (
        <ArrowUp className="size-3.5" weight="bold" />
      ) : (
        <ArrowDown className="size-3.5" weight="bold" />
      )}
      {Math.abs(value)}%
    </span>
  );
}
