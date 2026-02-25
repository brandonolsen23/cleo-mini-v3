import { Badge } from "@/components/ui/badge";
import { METHOD_LABELS, type ContactMethod } from "../../types/outreach";

const METHOD_VARIANTS: Record<string, "default" | "secondary" | "outline"> = {
  mail: "default",
  email: "secondary",
  called: "outline",
};

export default function ContactMethodBadge({ method }: { method: string }) {
  const label = METHOD_LABELS[method as ContactMethod] || method;
  const variant = METHOD_VARIANTS[method] || "secondary";
  return (
    <Badge variant={variant} className="text-[10px] px-1.5 py-0">
      {label}
    </Badge>
  );
}
