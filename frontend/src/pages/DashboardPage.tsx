import { PageHeader } from "@/components/ui/PageHeader";
import { StatCard } from "@/components/ui/StatCard";
import { StackedBarChart } from "@/components/ui/StackedBarChart";
import { MiniList } from "@/components/ui/MiniList";
import { Buildings, MapPin, Users } from "@phosphor-icons/react";
import { Text } from "@radix-ui/themes";
import { CHART_COLORS } from "@/lib/theme";
import { formatCompact } from "@/lib/utils";

// Placeholder data — will be replaced with real API calls
const CHART_DATA = Array.from({ length: 20 }, (_, i) => ({
  label: `${(i + 1).toString().padStart(2, "0")}`,
  retail: Math.floor(Math.random() * 400) + 100,
  industrial: Math.floor(Math.random() * 300) + 50,
  office: Math.floor(Math.random() * 200) + 30,
  other: Math.floor(Math.random() * 100) + 10,
}));

const TOP_CITIES = [
  { label: "London", value: 12, barPercent: 60 },
  { label: "Barrie", value: 8, barPercent: 40 },
  { label: "Windsor", value: 7, barPercent: 35 },
  { label: "Kingston", value: 5, barPercent: 25 },
];

const TOP_TYPES = [
  { label: "Retail", value: 34, barPercent: 85 },
  { label: "Industrial", value: 22, barPercent: 55 },
  { label: "Office", value: 18, barPercent: 45 },
  { label: "Multifamily", value: 14, barPercent: 35 },
];

const TOP_PARTIES = [
  { label: "Choice Properties REIT", value: 48, barPercent: 70 },
  { label: "RioCan Real Estate", value: 31, barPercent: 45 },
  { label: "SmartCentres REIT", value: 24, barPercent: 35 },
  { label: "Morguard Corporation", value: 18, barPercent: 26 },
];

export function DashboardPage() {
  return (
    <div className="flex flex-col gap-6">
      <PageHeader title="Dashboard" />

      {/* Stat cards row */}
      <div className="grid grid-cols-4 gap-6 rounded-[var(--card-radius)] border border-[var(--gray-6)] p-5">
        <StatCard
          label="Properties"
          value={19153}
          change={6.2}
          dotColor={CHART_COLORS.primary[0]}
        />
        <StatCard
          label="Transactions"
          value={15814}
          change={3.1}
          dotColor={CHART_COLORS.primary[1]}
        />
        <StatCard
          label="Parcels Resolved"
          value={28774}
          change={-2.4}
          dotColor={CHART_COLORS.primary[2]}
        />
        <StatCard
          label="Cities Covered"
          value={414}
          change={0}
          dotColor={CHART_COLORS.primary[3]}
        />
      </div>

      {/* Chart */}
      <div className="rounded-[var(--card-radius)] border border-[var(--gray-6)] p-5">
        <div className="mb-4 flex items-center justify-between">
          <Text size="3" weight="medium">
            Transaction Volume
          </Text>
        </div>
        <StackedBarChart
          data={CHART_DATA}
          xKey="label"
          series={[
            { key: "other", label: "Other" },
            { key: "office", label: "Office" },
            { key: "industrial", label: "Industrial" },
            { key: "retail", label: "Retail" },
          ]}
          height={280}
          formatYAxis={(v) => formatCompact(v)}
        />
      </div>

      {/* Mini lists row */}
      <div className="grid grid-cols-3 gap-4">
        <MiniList
          title="Top Cities"
          items={TOP_CITIES.map((c) => ({
            icon: <MapPin size={16} />,
            ...c,
          }))}
          onItemClick={() => {}}
        />
        <MiniList
          title="Property Types"
          items={TOP_TYPES.map((t) => ({
            icon: <Buildings size={16} />,
            ...t,
          }))}
          onItemClick={() => {}}
        />
        <MiniList
          title="Top Parties"
          items={TOP_PARTIES.map((p) => ({
            icon: <Users size={16} />,
            ...p,
          }))}
          onItemClick={() => {}}
        />
      </div>
    </div>
  );
}
