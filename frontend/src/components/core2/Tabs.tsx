import Icon from "./Icon";

type TabItem = {
    label?: string;
    icon?: string;
    value: string;
};

type TabsProps = {
    className?: string;
    items: TabItem[];
    value: string;
    onChange: (value: string) => void;
};

const Tabs = ({ className, items, value, onChange }: TabsProps) => (
    <div
        className={`inline-flex gap-0.5 rounded-3xl bg-b-surface1 p-1 ${className || ""}`}
    >
        {items.map((item) => (
            <button
                key={item.value}
                className={`inline-flex items-center gap-2 h-10 px-4 rounded-3xl text-button transition-all cursor-pointer ${
                    value === item.value
                        ? "bg-b-surface2 text-t-primary fill-t-primary shadow-widget"
                        : "text-t-secondary fill-t-secondary hover:text-t-primary hover:fill-t-primary"
                }`}
                onClick={() => onChange(item.value)}
            >
                {item.icon && (
                    <Icon className="!size-5 fill-inherit" name={item.icon} />
                )}
                {item.label}
            </button>
        ))}
    </div>
);

export default Tabs;
