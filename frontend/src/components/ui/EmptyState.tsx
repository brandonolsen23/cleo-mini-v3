import { Button } from "@radix-ui/themes";

interface EmptyStateProps {
  icon?: React.ReactNode;
  title: string;
  description?: string;
  action?: {
    label: string;
    onClick: () => void;
  };
}

export function EmptyState({
  icon,
  title,
  description,
  action,
}: EmptyStateProps) {
  return (
    <div className="flex flex-col items-center justify-center py-16">
      {icon && (
        <div className="mb-4 text-[var(--gray-8)]">{icon}</div>
      )}
      <span className="text-[16px] font-medium leading-[24px] text-[var(--gray-12)]">
        {title}
      </span>
      {description && (
        <span className="mt-1 max-w-sm text-center text-[14px] leading-[20px] text-[var(--gray-9)]">
          {description}
        </span>
      )}
      {action && (
        <Button
          variant="soft"
          size="2"
          className="mt-4"
          onClick={action.onClick}
        >
          {action.label}
        </Button>
      )}
    </div>
  );
}
