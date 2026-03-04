import { TabNav } from "@radix-ui/themes";

interface Tab {
  label: string;
  value: string;
}

interface PageHeaderProps {
  title: string;
  description?: string;
  tabs?: Tab[];
  activeTab?: string;
  onTabChange?: (value: string) => void;
  actions?: React.ReactNode;
}

export function PageHeader({
  title,
  description,
  tabs,
  activeTab,
  onTabChange,
  actions,
}: PageHeaderProps) {
  return (
    <div>
      <div className="flex items-start justify-between" style={{ minHeight: 32 }}>
        <div>
          {/* WorkOS uses heading-2: 24px, bold, 32px line-height */}
          <h2 className="text-[24px] font-medium leading-[32px] tracking-[0] text-[var(--gray-12)]">
            {title}
          </h2>
          {description && (
            <p className="mt-1 text-[14px] leading-[20px] text-[var(--gray-9)]">
              {description}
            </p>
          )}
        </div>
        {actions && <div className="flex items-center gap-2">{actions}</div>}
      </div>

      {tabs && tabs.length > 0 && (
        <TabNav.Root className="mt-4">
          {tabs.map((tab) => (
            <TabNav.Link
              key={tab.value}
              active={activeTab === tab.value}
              onClick={() => onTabChange?.(tab.value)}
              style={{ cursor: "pointer" }}
            >
              {tab.label}
            </TabNav.Link>
          ))}
        </TabNav.Root>
      )}
    </div>
  );
}
