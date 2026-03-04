import {
  LineChart,
  Line,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
} from "recharts";
import { Text } from "@radix-ui/themes";
import { CHART_COLORS } from "@/lib/theme";

interface SimpleLineChartProps {
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

export function SimpleLineChart({
  data,
  xKey,
  series,
  height = 300,
  formatYAxis,
}: SimpleLineChartProps) {
  return (
    <ResponsiveContainer width="100%" height={height}>
      <LineChart data={data}>
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
          <Line
            key={s.key}
            type="monotone"
            dataKey={s.key}
            name={s.label}
            stroke={CHART_COLORS.primary[i % CHART_COLORS.primary.length]}
            strokeWidth={2}
            dot={false}
            activeDot={{ r: 4, strokeWidth: 0 }}
          />
        ))}
      </LineChart>
    </ResponsiveContainer>
  );
}
