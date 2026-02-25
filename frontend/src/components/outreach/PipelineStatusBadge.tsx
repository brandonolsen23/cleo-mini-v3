import { cn } from "@/lib/utils";
import { PIPELINE_STATUS_LABELS } from "../../types/outreach";
import { STAGE_LABELS } from "../../types/crm";

// Radix step 8 backgrounds with high-contrast text
const statusColors: Record<string, string> = {
  // Pipeline statuses (property)
  not_started: "bg-[#bcbbb5] text-stone-900",
  attempted_contact: "bg-[#5eb1ef] text-blue-950",
  interested: "bg-[#3db9cf] text-cyan-950",
  listed: "bg-[#53b9ab] text-teal-950",
  do_not_contact: "bg-[#ec8e7b] text-red-950",
  // Deal stages
  active_deal: "bg-[#53b9ab] text-teal-950",
  in_negotiation: "bg-[#56ba9f] text-green-950",
  under_contract: "bg-[#65ba74] text-green-950",
  closed_won: "bg-[#8db654] text-lime-950",
  lost_cancelled: "bg-[#9b9ef0] text-indigo-950",
  // Legacy fallbacks
  closed_lost: "bg-red-200 text-red-900",
};

const allLabels: Record<string, string> = {
  ...PIPELINE_STATUS_LABELS,
  ...STAGE_LABELS,
};

export default function PipelineStatusBadge({ status }: { status: string }) {
  const label = allLabels[status] || status;
  return (
    <span
      className={cn(
        "inline-flex items-center px-2 py-0.5 rounded text-xs font-medium",
        statusColors[status] ?? "bg-[#bcbbb5] text-stone-900",
      )}
    >
      {label}
    </span>
  );
}
