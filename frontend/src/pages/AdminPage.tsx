import { PageHeader } from "@/components/ui/PageHeader";
import { Text } from "@radix-ui/themes";

export function AdminPage() {
  return (
    <div className="flex flex-col gap-6">
      <PageHeader
        title="Admin"
        description="System configuration and pipeline management."
      />
      <div className="rounded-[var(--card-radius)] border border-[var(--gray-6)] p-8 text-center">
        <Text size="2" color="gray">
          Admin tools and pipeline controls will be wired here.
        </Text>
      </div>
    </div>
  );
}
