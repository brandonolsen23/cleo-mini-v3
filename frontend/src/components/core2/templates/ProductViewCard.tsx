import { useState, useMemo } from "react";
import {
    BarChart,
    Bar,
    XAxis,
    Tooltip,
    ResponsiveContainer,
    Cell,
} from "recharts";
import Card from "../Card";
import Percentage from "../Percentage";

const defaultDurations = [
    { id: 1, name: "Last 7 days" },
    { id: 2, name: "Last month" },
    { id: 3, name: "Last year" },
];

const defaultChartData = [
    { name: "14", amt: 1145231 },
    { name: "15", amt: 1453134 },
    { name: "16", amt: 809435 },
    { name: "17", amt: 2204521 },
    { name: "18", amt: 1845105 },
    { name: "19", amt: 654104 },
    { name: "20", amt: 2004561 },
];

const CustomTooltip = ({ payload, prefix = "$", formatter }: { payload?: { value: number }[]; prefix?: string; formatter?: (v: number) => string }) => {
    if (payload && payload.length) {
        const val = payload[0].value;
        const display = formatter ? formatter(val) : `${prefix}${val.toLocaleString()}`;
        return (
            <div className="rounded-lg bg-shade-02 px-3 py-1.5 text-caption text-t-light shadow-dropdown">
                {display}
            </div>
        );
    }
    return null;
};

type ProductViewCardProps = {
    title?: string;
    subtitle?: string;
    chartData?: { name: string; amt: number }[];
    totalValue?: string;
    totalPrefix?: string;
    percentChange?: number | null;
    percentLabel?: string;
    tooltipFormatter?: (value: number) => string;
    durations?: { id: number; name: string }[];
    selectedDuration?: { id: number; name: string };
    onDurationChange?: (value: { id: number; name: string }) => void;
};

const ProductViewCard = ({
    title = "Product view",
    subtitle,
    chartData,
    totalValue,
    totalPrefix = "$",
    percentChange,
    percentLabel = "vs last month",
    tooltipFormatter,
    durations,
    selectedDuration,
    onDurationChange,
}: ProductViewCardProps) => {
    const durs = durations ?? defaultDurations;
    const data = chartData ?? defaultChartData;
    const [internalDuration, setInternalDuration] = useState(durs[0]);

    const duration = selectedDuration ?? internalDuration;
    const setDuration = onDurationChange ?? setInternalDuration;

    const displayValue = totalValue ?? "10.2m";
    const displayPercent = percentChange ?? 36.8;

    const getMinValues = useMemo(() => {
        const sortedData = [...data].sort((a, b) => a.amt - b.amt);
        return [sortedData[0]?.amt, sortedData[1]?.amt];
    }, [data]);

    return (
        <Card
            title={title}
            subtitle={subtitle}
            selectValue={duration}
            selectOnChange={setDuration}
            selectOptions={durs}
        >
            <div className="pt-6 px-5 pb-5">
                <div className="flex items-end">
                    <div className="shrink-0 w-52 mr-18">
                        <div className="flex mb-4">
                            <div className="text-h3 text-t-tertiary">{totalPrefix}</div>
                            <div className="text-h2">{displayValue}</div>
                        </div>
                        <div className="flex items-center gap-2">
                            <Percentage value={displayPercent} />
                            <div className="text-caption text-t-tertiary">
                                {percentLabel}
                            </div>
                        </div>
                    </div>
                    <div className="grow h-74">
                        <ResponsiveContainer width="100%" height="100%">
                            <BarChart
                                data={data}
                                margin={{
                                    top: 0,
                                    right: 0,
                                    left: 0,
                                    bottom: 0,
                                }}
                            >
                                <XAxis
                                    dataKey="name"
                                    axisLine={false}
                                    tickLine={false}
                                    tick={{
                                        fontSize: "12px",
                                        fill: "#a1a1a1",
                                    }}
                                    height={32}
                                    dy={10}
                                />
                                <Tooltip
                                    content={<CustomTooltip prefix={totalPrefix} formatter={tooltipFormatter} />}
                                    cursor={false}
                                />
                                <Bar
                                    dataKey="amt"
                                    activeBar={{
                                        fill: "#83bf6e",
                                        fillOpacity: 1,
                                    }}
                                    radius={6}
                                >
                                    {data.map((entry, index) => (
                                        <Cell
                                            key={`cell-${index}`}
                                            fill={
                                                getMinValues.includes(entry.amt)
                                                    ? "#d4d4d4"
                                                    : "#a1a1a1"
                                            }
                                            fillOpacity={
                                                getMinValues.includes(entry.amt)
                                                    ? 1
                                                    : 0.4
                                            }
                                        />
                                    ))}
                                </Bar>
                            </BarChart>
                        </ResponsiveContainer>
                    </div>
                </div>
            </div>
        </Card>
    );
};

export default ProductViewCard;
