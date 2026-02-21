import { cn } from "@/lib/utils";
import type { DealStage } from "../../types/crm";
import { STAGE_LABELS } from "../../types/crm";

const stageColors: Record<DealStage, string> = {
  lead: "bg-gray-100 text-gray-700",
  contacted: "bg-blue-100 text-blue-700",
  negotiating: "bg-yellow-100 text-yellow-700",
  under_contract: "bg-purple-100 text-purple-700",
  closed_won: "bg-green-100 text-green-700",
  closed_lost: "bg-red-100 text-red-700",
};

export default function DealStageBadge({ stage }: { stage: DealStage }) {
  return (
    <span
      className={cn(
        "inline-flex items-center px-2 py-0.5 rounded text-xs font-medium",
        stageColors[stage] ?? "bg-gray-100 text-gray-700",
      )}
    >
      {STAGE_LABELS[stage] ?? stage}
    </span>
  );
}
