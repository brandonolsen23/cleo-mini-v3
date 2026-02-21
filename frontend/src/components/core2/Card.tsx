import Select from "./Select";

type CardProps = {
    className?: string;
    classHead?: string;
    title: string;
    subtitle?: string;
    children: React.ReactNode;
    selectOptions?: { id: number; name: string }[];
    selectValue?: {
        id: number;
        name: string;
    };
    selectOnChange?: (value: { id: number; name: string }) => void;
    headContent?: React.ReactNode;
};

const Card = ({
    className,
    classHead,
    title,
    subtitle,
    selectOptions,
    selectValue,
    selectOnChange,
    children,
    headContent,
}: CardProps) => (
    <div className={`card ${className || ""}`}>
        <div
            className={`flex items-center h-12 pl-5 ${
                classHead || ""
            }`}
        >
            <div className="mr-auto">
                <div className="text-h6">{title}</div>
                {subtitle && <div className="text-body-2 text-t-secondary">{subtitle}</div>}
            </div>
            {headContent}
            {selectOptions && selectValue && selectOnChange && (
                <Select
                    className="min-w-40"
                    value={selectValue}
                    onChange={selectOnChange}
                    options={selectOptions}
                />
            )}
        </div>
        <div className="pt-3">{children}</div>
    </div>
);

export default Card;
