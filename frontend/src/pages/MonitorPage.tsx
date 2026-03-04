import { PageHeader } from "@/components/ui/PageHeader";
import { Text } from "@radix-ui/themes";

export function MonitorPage() {
  return (
    <div className="flex flex-col gap-6">
      <PageHeader
        title="Monitor"
        description="Pipeline health and data quality metrics."
      />
      <div className="rounded-[var(--card-radius)] border border-[var(--gray-6)] p-8 text-center">
        <Text size="2" color="gray">
          Pipeline monitoring dashboard will be wired here.
        </Text>
      </div>
    </div>
  );
}
