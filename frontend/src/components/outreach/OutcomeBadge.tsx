import { cn } from "@/lib/utils";
import { OUTCOME_LABELS, type OutcomeType } from "../../types/outreach";

const outcomeColors: Record<string, string> = {
  no_answer: "bg-gray-100 text-gray-600",
  left_vm: "bg-amber-100 text-amber-700",
  sent: "bg-blue-100 text-blue-700",
  spoke_with: "bg-green-100 text-green-700",
  bounced: "bg-red-100 text-red-600",
};

export default function OutcomeBadge({ outcome }: { outcome: string }) {
  const label = OUTCOME_LABELS[outcome as OutcomeType] || outcome;
  return (
    <span
      className={cn(
        "inline-flex items-center px-1.5 py-0 rounded text-[10px] font-medium",
        outcomeColors[outcome] ?? "bg-gray-100 text-gray-600",
      )}
    >
      {label}
    </span>
  );
}
