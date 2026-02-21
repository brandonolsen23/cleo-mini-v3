import Checkbox from "./Checkbox";

type TableProps = {
    className?: string;
    children: React.ReactNode;
    headers: string[];
    selectAll?: boolean;
    onSelectAll?: (checked: boolean) => void;
    allSelected?: boolean;
};

const Table = ({
    className,
    children,
    headers,
    selectAll,
    onSelectAll,
    allSelected,
}: TableProps) => (
    <div className={`overflow-x-auto ${className || ""}`}>
        <table className="w-full">
            <thead>
                <tr className="border-b border-s">
                    {selectAll && (
                        <th className="w-12 py-3 pl-4">
                            <Checkbox
                                checked={allSelected || false}
                                onChange={(val) => onSelectAll?.(val)}
                            />
                        </th>
                    )}
                    {headers.map((header, index) => (
                        <th
                            key={index}
                            className="py-3 px-4 text-left text-caption font-semibold text-t-secondary uppercase tracking-wider"
                        >
                            {header}
                        </th>
                    ))}
                </tr>
            </thead>
            <tbody>{children}</tbody>
        </table>
    </div>
);

export default Table;
