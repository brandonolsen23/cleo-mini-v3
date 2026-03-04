import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { Text, Badge } from "@radix-ui/themes";
import { createColumnHelper } from "@tanstack/react-table";
import { PageHeader } from "@/components/ui/PageHeader";
import { SearchToolbar, FilterIcons } from "@/components/ui/SearchToolbar";
import { DataTable } from "@/components/ui/DataTable";

interface TransactionRow {
  rt_id: string;
  address: string;
  city: string;
  price: string;
  date: string;
  type: string;
}

const SAMPLE: TransactionRow[] = Array.from({ length: 40 }, (_, i) => ({
  rt_id: `RT${10000 + i}`,
  address: `${200 + i * 3} Queen Street`,
  city: ["London", "Barrie", "Windsor", "Kingston", "Hamilton"][i % 5],
  price: `$${(Math.floor(Math.random() * 80) * 100000 + 200000).toLocaleString()}`,
  date: `2025-${String((i % 12) + 1).padStart(2, "0")}-${String((i % 28) + 1).padStart(2, "0")}`,
  type: ["Retail", "Industrial", "Office", "Multifamily"][i % 4],
}));

const col = createColumnHelper<TransactionRow>();

const columns = [
  col.accessor("rt_id", {
    header: "RT ID",
    cell: (info) => (
      <Text size="2" weight="medium" color="blue">
        {info.getValue()}
      </Text>
    ),
  }),
  col.accessor("address", { header: "Address" }),
  col.accessor("city", { header: "City" }),
  col.accessor("type", {
    header: "Type",
    cell: (info) => (
      <Badge size="1" variant="soft" color="gray">
        {info.getValue()}
      </Badge>
    ),
  }),
  col.accessor("price", { header: "Price" }),
  col.accessor("date", { header: "Date" }),
];

export function TransactionsPage() {
  const [search, setSearch] = useState("");
  const navigate = useNavigate();

  return (
    <div className="flex flex-col gap-6">
      <PageHeader title="Transactions" description="All Realtrack transaction records." />

      <div className="flex flex-col gap-4">
        <SearchToolbar
          value={search}
          onChange={setSearch}
          placeholder="Search by address, RT ID, or party..."
          filters={[
            { label: "Property type", icon: FilterIcons.add, onClick: () => {} },
            { label: "Date range", icon: FilterIcons.calendar, onClick: () => {} },
          ]}
        />

        <DataTable
          data={SAMPLE}
          columns={columns}
          globalFilter={search}
          pageSize={20}
          onRowClick={(row) => navigate(`/transactions/${row.rt_id}`)}
        />
      </div>
    </div>
  );
}
