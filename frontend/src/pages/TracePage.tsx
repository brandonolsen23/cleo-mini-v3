import { PageHeader } from "@/components/ui/PageHeader";
import { Text } from "@radix-ui/themes";

export function TracePage() {
  return (
    <div className="flex flex-col gap-6">
      <PageHeader
        title="Trace"
        description="Trace a record through the full pipeline."
      />
      <div className="rounded-[var(--card-radius)] border border-[var(--gray-6)] p-8 text-center">
        <Text size="2" color="gray">
          Pipeline trace tool will be wired here.
        </Text>
      </div>
    </div>
  );
}
