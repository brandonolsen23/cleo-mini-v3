import {
  BarChart,
  Bar,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
} from "recharts";
import { Text } from "@radix-ui/themes";
import { CHART_COLORS } from "@/lib/theme";

interface StackedBarChartProps {
  data: Record<string, unknown>[];
  xKey: string;
  series: { key: string; label: string }[];
  height?: number;
  formatYAxis?: (value: number) => string;
}

// eslint-disable-next-line @typescript-eslint/no-explicit-any
function CustomTooltip({ active, payload, label }: any) {
  if (!active || !payload?.length) return null;

  return (
    <div className="rounded-[var(--radius-3)] border border-[var(--gray-6)] bg-white px-3 py-2 shadow-[var(--elevation-2)]">
      <Text size="1" weight="medium" className="mb-1 block">
        {label}
      </Text>
      {/* eslint-disable-next-line @typescript-eslint/no-explicit-any */}
      {payload.map((entry: any, i: number) => (
        <div key={i} className="flex items-center gap-2">
          <span
            className="h-2 w-2 rounded-full"
            style={{ backgroundColor: entry.color }}
          />
          <Text size="1" color="gray">
            {entry.name}: {entry.value?.toLocaleString()}
          </Text>
        </div>
      ))}
    </div>
  );
}

export function StackedBarChart({
  data,
  xKey,
  series,
  height = 300,
  formatYAxis,
}: StackedBarChartProps) {
  return (
    <ResponsiveContainer width="100%" height={height}>
      <BarChart data={data} barCategoryGap="20%">
        <CartesianGrid
          strokeDasharray="none"
          vertical={false}
          stroke="var(--gray-4)"
        />
        <XAxis
          dataKey={xKey}
          tick={{ fontSize: 12, fill: "var(--gray-9)" }}
          tickLine={false}
          axisLine={{ stroke: "var(--gray-4)" }}
        />
        <YAxis
          tick={{ fontSize: 12, fill: "var(--gray-9)" }}
          tickLine={false}
          axisLine={false}
          tickFormatter={formatYAxis}
        />
        <Tooltip content={<CustomTooltip />} />
        {series.map((s, i) => (
          <Bar
            key={s.key}
            dataKey={s.key}
            name={s.label}
            stackId="stack"
            fill={CHART_COLORS.primary[i % CHART_COLORS.primary.length]}
            radius={
              i === series.length - 1 ? [3, 3, 0, 0] : [0, 0, 0, 0]
            }
          />
        ))}
      </BarChart>
    </ResponsiveContainer>
  );
}
