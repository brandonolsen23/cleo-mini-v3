import { cn } from "@/lib/utils";
import type { DealStage } from "../../types/crm";
import { STAGE_LABELS } from "../../types/crm";

// Radix step 8 backgrounds with high-contrast text
const stageColors: Record<string, string> = {
  active_deal: "bg-[#53b9ab] text-teal-950",
  in_negotiation: "bg-[#56ba9f] text-green-950",
  under_contract: "bg-[#65ba74] text-green-950",
  closed_won: "bg-[#8db654] text-lime-950",
  lost_cancelled: "bg-[#9b9ef0] text-indigo-950",
  // legacy
  lead: "bg-gray-200 text-gray-800",
  contacted: "bg-sky-200 text-sky-800",
  qualifying: "bg-blue-200 text-blue-800",
  negotiating: "bg-yellow-200 text-yellow-800",
  closed_lost: "bg-red-200 text-red-800",
};

export default function DealStageBadge({ stage }: { stage: DealStage }) {
  return (
    <span
      className={cn(
        "inline-flex items-center px-2 py-0.5 rounded text-xs font-medium",
        stageColors[stage] ?? "bg-gray-200 text-gray-800",
      )}
    >
      {STAGE_LABELS[stage] ?? stage}
    </span>
  );
}
