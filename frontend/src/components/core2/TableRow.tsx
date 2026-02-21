import Checkbox from "./Checkbox";

type TableRowProps = {
    className?: string;
    children: React.ReactNode;
    selectable?: boolean;
    selected?: boolean;
    onSelect?: (checked: boolean) => void;
};

const TableRow = ({
    className,
    children,
    selectable,
    selected,
    onSelect,
}: TableRowProps) => (
    <tr
        className={`border-b border-s last:border-b-0 transition-colors hover:bg-b-highlight ${
            selected ? "bg-blue-light/50" : ""
        } ${className || ""}`}
    >
        {selectable && (
            <td className="w-12 py-3 pl-4">
                <Checkbox
                    checked={selected || false}
                    onChange={(val) => onSelect?.(val)}
                />
            </td>
        )}
        {children}
    </tr>
);

export default TableRow;
