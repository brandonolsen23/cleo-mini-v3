import { useState } from "react";
import {
  Text,
  Heading,
  Button,
  Badge,
  TextField,
  TextArea,
  Select,
  Checkbox,
  Switch,
  Separator,
  Tooltip,
  Dialog,
  DropdownMenu,
  IconButton,
  Card,
  Code,
  Callout,
  DataList,
  Avatar,
  Tabs,
} from "@radix-ui/themes";
import {
  MagnifyingGlass,
  Plus,
  DotsThree,
  Info,
  Buildings,
  MapPin,
  Trash,
  PencilSimple,
  Copy,
  CaretDown,
  Check,
  Warning,
  Export,
  Funnel,
} from "@phosphor-icons/react";
import { createColumnHelper } from "@tanstack/react-table";
import { PageHeader } from "@/components/ui/PageHeader";
import { SearchToolbar, FilterIcons } from "@/components/ui/SearchToolbar";
import { DataTable } from "@/components/ui/DataTable";
import { StatCard } from "@/components/ui/StatCard";
import { MiniList } from "@/components/ui/MiniList";
import { StackedBarChart } from "@/components/ui/StackedBarChart";
import { SimpleLineChart } from "@/components/ui/SimpleLineChart";
import { EmptyState } from "@/components/ui/EmptyState";
import { Pagination } from "@/components/ui/Pagination";
import { CHART_COLORS } from "@/lib/theme";
import { formatCompact } from "@/lib/utils";

/* ── Section wrapper ─────────────────────────────────────────────── */

function Section({
  title,
  children,
}: {
  title: string;
  children: React.ReactNode;
}) {
  return (
    <section className="mb-12">
      <Heading size="4" weight="bold" className="mb-4">
        {title}
      </Heading>
      <Separator size="4" className="mb-6" />
      {children}
    </section>
  );
}

/* ── Sample table data ───────────────────────────────────────────── */

interface DemoRow {
  name: string;
  email: string;
  role: string;
  status: "active" | "inactive" | "pending";
  joined: string;
}

const TABLE_DATA: DemoRow[] = [
  { name: "Alice Johnson", email: "alice@example.com", role: "Admin", status: "active", joined: "2025-01-15" },
  { name: "Bob Smith", email: "bob@example.com", role: "Editor", status: "active", joined: "2025-02-20" },
  { name: "Carol Davis", email: "carol@example.com", role: "Viewer", status: "pending", joined: "2025-03-01" },
  { name: "David Lee", email: "david@example.com", role: "Editor", status: "inactive", joined: "2024-11-10" },
  { name: "Eve Martinez", email: "eve@example.com", role: "Admin", status: "active", joined: "2024-08-05" },
  { name: "Frank Wilson", email: "frank@example.com", role: "Viewer", status: "active", joined: "2025-01-22" },
  { name: "Grace Chen", email: "grace@example.com", role: "Editor", status: "pending", joined: "2025-02-28" },
  { name: "Henry Brown", email: "henry@example.com", role: "Viewer", status: "inactive", joined: "2024-09-15" },
];

const tCol = createColumnHelper<DemoRow>();

const TABLE_COLUMNS = [
  tCol.accessor("name", {
    header: "Name",
    cell: (info) => (
      <Text size="2" weight="medium">
        {info.getValue()}
      </Text>
    ),
  }),
  tCol.accessor("email", { header: "Email" }),
  tCol.accessor("role", {
    header: "Role",
    cell: (info) => (
      <Badge size="1" variant="soft" color="gray">
        {info.getValue()}
      </Badge>
    ),
  }),
  tCol.accessor("status", {
    header: "Status",
    cell: (info) => {
      const v = info.getValue();
      const color = v === "active" ? "green" : v === "pending" ? "orange" : "gray";
      return (
        <Badge size="1" variant="soft" color={color}>
          {v}
        </Badge>
      );
    },
  }),
  tCol.accessor("joined", { header: "Joined" }),
];

/* ── Chart data ──────────────────────────────────────────────────── */

const BAR_DATA = Array.from({ length: 16 }, (_, i) => ({
  time: `${((i + 1) % 12 || 12)}${i < 12 ? "pm" : "am"}`,
  allowed: Math.floor(Math.random() * 3000) + 1000,
  challenged: Math.floor(Math.random() * 800) + 200,
  blocked: Math.floor(Math.random() * 400) + 50,
}));

const LINE_DATA = Array.from({ length: 12 }, (_, i) => ({
  month: ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"][i],
  transactions: Math.floor(Math.random() * 500) + 200,
  properties: Math.floor(Math.random() * 300) + 100,
}));

/* ── Showcase ────────────────────────────────────────────────────── */

export function ShowcasePage() {
  const [search, setSearch] = useState("");
  const [tab, setTab] = useState("overview");
  const [page, setPage] = useState(3);
  const [checked, setChecked] = useState(false);
  const [switched, setSwitched] = useState(true);
  const [selectVal, setSelectVal] = useState("editor");

  return (
    <div className="flex flex-col gap-6">
      <PageHeader
        title="Design System"
        description="Complete component reference — all elements mirror the WorkOS dashboard styling."
        tabs={[
          { label: "Overview", value: "overview" },
          { label: "Components", value: "components" },
          { label: "Patterns", value: "patterns" },
        ]}
        activeTab={tab}
        onTabChange={setTab}
      />

      {/* ── Typography ─────────────────────────────────────────── */}
      <Section title="Typography">
        <div className="space-y-3">
          <Heading size="8">Heading size 8 (35px)</Heading>
          <Heading size="7">Heading size 7 (28px)</Heading>
          <Heading size="6">Heading size 6 (24px)</Heading>
          <Heading size="5">Heading size 5 (20px)</Heading>
          <Heading size="4">Heading size 4 (18px)</Heading>
          <Heading size="3">Heading size 3 (16px)</Heading>
          <Separator size="4" className="my-4" />
          <Text size="4" as="p">
            Body text size 4 — The quick brown fox jumps over the lazy dog.
          </Text>
          <Text size="3" as="p">
            Body text size 3 — The quick brown fox jumps over the lazy dog.
          </Text>
          <Text size="2" as="p">
            Body text size 2 (default table/UI text) — The quick brown fox jumps over the lazy dog.
          </Text>
          <Text size="1" as="p" color="gray">
            Body text size 1 (captions/labels) — The quick brown fox jumps over the lazy dog.
          </Text>
          <div className="mt-2">
            <Code size="2">code text — monospace</Code>
          </div>
        </div>
      </Section>

      {/* ── Buttons ────────────────────────────────────────────── */}
      <Section title="Buttons">
        <div className="space-y-4">
          <div>
            <Text size="1" color="gray" weight="medium" className="mb-2 block">
              Variants
            </Text>
            <div className="flex flex-wrap items-center gap-3">
              <Button size="2">Solid (default)</Button>
              <Button size="2" variant="soft">
                Soft
              </Button>
              <Button size="2" variant="outline">
                Outline
              </Button>
              <Button size="2" variant="ghost">
                Ghost
              </Button>
              <Button size="2" color="red">
                Destructive
              </Button>
              <Button size="2" disabled>
                Disabled
              </Button>
            </div>
          </div>

          <div>
            <Text size="1" color="gray" weight="medium" className="mb-2 block">
              Sizes
            </Text>
            <div className="flex flex-wrap items-center gap-3">
              <Button size="1">Size 1</Button>
              <Button size="2">Size 2</Button>
              <Button size="3">Size 3</Button>
            </div>
          </div>

          <div>
            <Text size="1" color="gray" weight="medium" className="mb-2 block">
              With icons
            </Text>
            <div className="flex flex-wrap items-center gap-3">
              <Button size="2">
                <Plus size={14} weight="bold" />
                Add Property
              </Button>
              <Button size="2" variant="soft">
                <Export size={14} />
                Export
              </Button>
              <Button size="2" variant="outline">
                <Funnel size={14} />
                Filter
              </Button>
              <IconButton size="2" variant="soft" color="gray">
                <DotsThree size={16} weight="bold" />
              </IconButton>
            </div>
          </div>
        </div>
      </Section>

      {/* ── Badges ─────────────────────────────────────────────── */}
      <Section title="Badges">
        <div className="space-y-4">
          <div>
            <Text size="1" color="gray" weight="medium" className="mb-2 block">
              Colors (soft variant)
            </Text>
            <div className="flex flex-wrap gap-2">
              <Badge size="1" variant="soft">Default</Badge>
              <Badge size="1" variant="soft" color="blue">Blue</Badge>
              <Badge size="1" variant="soft" color="green">Green</Badge>
              <Badge size="1" variant="soft" color="red">Red</Badge>
              <Badge size="1" variant="soft" color="orange">Orange</Badge>
              <Badge size="1" variant="soft" color="purple">Purple</Badge>
              <Badge size="1" variant="soft" color="gray">Gray</Badge>
              <Badge size="1" variant="soft" color="indigo">Indigo</Badge>
              <Badge size="1" variant="soft" color="cyan">Cyan</Badge>
            </div>
          </div>
          <div>
            <Text size="1" color="gray" weight="medium" className="mb-2 block">
              Variants
            </Text>
            <div className="flex flex-wrap gap-2">
              <Badge size="2" variant="soft">Soft</Badge>
              <Badge size="2" variant="solid">Solid</Badge>
              <Badge size="2" variant="outline">Outline</Badge>
              <Badge size="2" variant="surface">Surface</Badge>
            </div>
          </div>
          <div>
            <Text size="1" color="gray" weight="medium" className="mb-2 block">
              Sizes
            </Text>
            <div className="flex flex-wrap items-center gap-2">
              <Badge size="1" variant="soft" color="blue">Size 1</Badge>
              <Badge size="2" variant="soft" color="blue">Size 2</Badge>
              <Badge size="3" variant="soft" color="blue">Size 3</Badge>
            </div>
          </div>
          <div>
            <Text size="1" color="gray" weight="medium" className="mb-2 block">
              Badge vs Pill (radius)
            </Text>
            <div className="flex flex-wrap items-center gap-4">
              <div className="flex flex-col items-start gap-1.5">
                <Text size="1" className="text-[var(--gray-9)]">Badge (default)</Text>
                <div className="flex gap-2">
                  <Badge size="1" variant="soft" color="green">Active</Badge>
                  <Badge size="1" variant="outline" color="gray">RT175216</Badge>
                  <Badge size="1" variant="soft" color="jade">QSR</Badge>
                </div>
              </div>
              <div className="flex flex-col items-start gap-1.5">
                <Text size="1" className="text-[var(--gray-9)]">Pill (radius=full)</Text>
                <div className="flex gap-2">
                  <Badge size="1" variant="soft" color="green" radius="full">Active</Badge>
                  <Badge size="1" variant="outline" color="gray" radius="full">RT175216</Badge>
                  <Badge size="1" variant="soft" color="jade" radius="full">QSR</Badge>
                </div>
              </div>
            </div>
          </div>
        </div>
      </Section>

      {/* ── Form Controls ──────────────────────────────────────── */}
      <Section title="Form Controls">
        <div className="grid max-w-2xl grid-cols-2 gap-6">
          <div className="space-y-4">
            <div>
              <Text as="label" size="2" weight="medium" className="mb-1.5 block">
                Text input
              </Text>
              <TextField.Root size="2" placeholder="Enter value..." />
            </div>

            <div>
              <Text as="label" size="2" weight="medium" className="mb-1.5 block">
                Search input
              </Text>
              <TextField.Root size="2" placeholder="Search...">
                <TextField.Slot>
                  <MagnifyingGlass size={16} />
                </TextField.Slot>
              </TextField.Root>
            </div>

            <div>
              <Text as="label" size="2" weight="medium" className="mb-1.5 block">
                Textarea
              </Text>
              <TextArea size="2" placeholder="Enter description..." />
            </div>
          </div>

          <div className="space-y-4">
            <div>
              <Text as="label" size="2" weight="medium" className="mb-1.5 block">
                Select
              </Text>
              <Select.Root
                size="2"
                value={selectVal}
                onValueChange={setSelectVal}
              >
                <Select.Trigger className="w-full" />
                <Select.Content>
                  <Select.Item value="admin">Admin</Select.Item>
                  <Select.Item value="editor">Editor</Select.Item>
                  <Select.Item value="viewer">Viewer</Select.Item>
                </Select.Content>
              </Select.Root>
            </div>

            <div className="flex items-center gap-6 pt-2">
              <label className="flex items-center gap-2">
                <Checkbox
                  checked={checked}
                  onCheckedChange={(v) => setChecked(v === true)}
                />
                <Text size="2">Checkbox</Text>
              </label>

              <label className="flex items-center gap-2">
                <Switch
                  checked={switched}
                  onCheckedChange={setSwitched}
                />
                <Text size="2">Switch</Text>
              </label>
            </div>

            <div>
              <Text as="label" size="2" weight="medium" className="mb-1.5 block">
                Input sizes
              </Text>
              <div className="space-y-2">
                <TextField.Root size="1" placeholder="Size 1" />
                <TextField.Root size="2" placeholder="Size 2 (default)" />
                <TextField.Root size="3" placeholder="Size 3" />
              </div>
            </div>
          </div>
        </div>
      </Section>

      {/* ── Search Toolbar ─────────────────────────────────────── */}
      <Section title="Search Toolbar">
        <SearchToolbar
          value={search}
          onChange={setSearch}
          placeholder="Search records..."
          filters={[
            { label: "Event type", icon: FilterIcons.add, onClick: () => {} },
            { label: "Date range", icon: FilterIcons.calendar, onClick: () => {} },
            { label: "Status", icon: FilterIcons.add, onClick: () => {}, active: true },
          ]}
        />
        <Text size="1" color="gray">
          Current search value: &quot;{search}&quot;
        </Text>
      </Section>

      {/* ── Data Table ─────────────────────────────────────────── */}
      <Section title="Data Table">
        <DataTable
          data={TABLE_DATA}
          columns={TABLE_COLUMNS}
          globalFilter={search}
          pageSize={5}
          onRowClick={(row) => alert(`Clicked: ${row.name}`)}
        />
      </Section>

      {/* ── Stat Cards ─────────────────────────────────────────── */}
      <Section title="Stat Cards">
        <div className="grid grid-cols-4 gap-6 rounded-[var(--card-radius)] border border-[var(--gray-6)] p-5">
          <StatCard
            label="Total Events"
            value={72500}
            change={6}
            dotColor={CHART_COLORS.primary[0]}
          />
          <StatCard
            label="Allowed"
            value={54400}
            change={12}
            dotColor={CHART_COLORS.primary[1]}
          />
          <StatCard
            label="Challenged"
            value={11300}
            change={-8}
            dotColor={CHART_COLORS.primary[2]}
          />
          <StatCard
            label="Blocked"
            value={6800}
            change={24}
            dotColor={CHART_COLORS.primary[3]}
          />
        </div>
      </Section>

      {/* ── Charts ─────────────────────────────────────────────── */}
      <Section title="Charts">
        <div className="space-y-8">
          <div>
            <Text size="2" weight="bold" className="mb-4 block">
              Stacked Bar Chart
            </Text>
            <StackedBarChart
              data={BAR_DATA}
              xKey="time"
              series={[
                { key: "blocked", label: "Blocked" },
                { key: "challenged", label: "Challenged" },
                { key: "allowed", label: "Allowed" },
              ]}
              height={280}
              formatYAxis={(v) => formatCompact(v)}
            />
          </div>
          <div>
            <Text size="2" weight="bold" className="mb-4 block">
              Line Chart
            </Text>
            <SimpleLineChart
              data={LINE_DATA}
              xKey="month"
              series={[
                { key: "transactions", label: "Transactions" },
                { key: "properties", label: "Properties" },
              ]}
              height={240}
            />
          </div>
        </div>
      </Section>

      {/* ── Mini Lists ─────────────────────────────────────────── */}
      <Section title="Mini Lists">
        <div className="grid grid-cols-3 gap-4">
          <MiniList
            title="Cities"
            items={[
              { icon: <MapPin size={16} />, label: "London", value: 12, barPercent: 60 },
              { icon: <MapPin size={16} />, label: "Barrie", value: 8, barPercent: 40 },
              { icon: <MapPin size={16} />, label: "Windsor", value: 7, barPercent: 35 },
              { icon: <MapPin size={16} />, label: "Kingston", value: 5, barPercent: 25 },
            ]}
            onItemClick={() => {}}
          />
          <MiniList
            title="Property Types"
            items={[
              { icon: <Buildings size={16} />, label: "Retail", value: 34, barPercent: 85 },
              { icon: <Buildings size={16} />, label: "Industrial", value: 22, barPercent: 55 },
              { icon: <Buildings size={16} />, label: "Office", value: 18, barPercent: 45 },
              { icon: <Buildings size={16} />, label: "Multifamily", value: 14, barPercent: 35 },
            ]}
            onItemClick={() => {}}
          />
          <MiniList
            title="Sources"
            items={[
              { label: "Realtrack", value: "15,814", barPercent: 90 },
              { label: "GeoWarehouse", value: "448", barPercent: 15 },
              { label: "Brands", value: "14,340", barPercent: 70 },
              { label: "OSM", value: "6,077", barPercent: 35 },
            ]}
          />
        </div>
      </Section>

      {/* ── Pagination ─────────────────────────────────────────── */}
      <Section title="Pagination">
        <Pagination
          currentPage={page}
          totalPages={10}
          onPageChange={setPage}
        />
      </Section>

      {/* ── Avatars ────────────────────────────────────────────── */}
      <Section title="Avatars">
        <div className="flex items-center gap-3">
          <Avatar size="1" fallback="A" />
          <Avatar size="2" fallback="BJ" color="blue" />
          <Avatar size="3" fallback="CD" color="green" />
          <Avatar size="4" fallback="EF" color="orange" />
          <Avatar size="5" fallback="GH" color="purple" />
        </div>
      </Section>

      {/* ── Cards ──────────────────────────────────────────────── */}
      <Section title="Cards">
        <div className="grid grid-cols-3 gap-4">
          <Card size="2">
            <div className="space-y-2">
              <Text size="2" weight="bold">
                Card Title
              </Text>
              <Text size="2" color="gray">
                A simple card with surface styling from Radix Themes.
              </Text>
              <Button size="1" variant="soft">
                Action
              </Button>
            </div>
          </Card>
          <Card size="2" variant="classic">
            <div className="space-y-2">
              <Text size="2" weight="bold">
                Classic Variant
              </Text>
              <Text size="2" color="gray">
                The classic card variant has a subtle shadow effect.
              </Text>
            </div>
          </Card>
          <Card size="2" variant="ghost">
            <div className="space-y-2">
              <Text size="2" weight="bold">
                Ghost Variant
              </Text>
              <Text size="2" color="gray">
                Ghost cards have no border or shadow — just content.
              </Text>
            </div>
          </Card>
        </div>
      </Section>

      {/* ── Callouts ───────────────────────────────────────────── */}
      <Section title="Callouts">
        <div className="max-w-xl space-y-3">
          <Callout.Root size="1">
            <Callout.Icon>
              <Info size={16} />
            </Callout.Icon>
            <Callout.Text>
              Default callout — informational message.
            </Callout.Text>
          </Callout.Root>
          <Callout.Root size="1" color="green">
            <Callout.Icon>
              <Check size={16} />
            </Callout.Icon>
            <Callout.Text>
              Success — operation completed successfully.
            </Callout.Text>
          </Callout.Root>
          <Callout.Root size="1" color="orange">
            <Callout.Icon>
              <Warning size={16} />
            </Callout.Icon>
            <Callout.Text>
              Warning — please review before proceeding.
            </Callout.Text>
          </Callout.Root>
          <Callout.Root size="1" color="red">
            <Callout.Icon>
              <Warning size={16} />
            </Callout.Icon>
            <Callout.Text>
              Error — something went wrong.
            </Callout.Text>
          </Callout.Root>
        </div>
      </Section>

      {/* ── Data List ──────────────────────────────────────────── */}
      <Section title="Data List">
        <div className="max-w-md">
          <DataList.Root>
            <DataList.Item>
              <DataList.Label>Property ID</DataList.Label>
              <DataList.Value>PRO_00142</DataList.Value>
            </DataList.Item>
            <DataList.Item>
              <DataList.Label>ARN</DataList.Label>
              <DataList.Value>
                <Code>01234567890123456789</Code>
              </DataList.Value>
            </DataList.Item>
            <DataList.Item>
              <DataList.Label>Status</DataList.Label>
              <DataList.Value>
                <Badge size="1" variant="soft" color="green">
                  Resolved
                </Badge>
              </DataList.Value>
            </DataList.Item>
            <DataList.Item>
              <DataList.Label>Sources</DataList.Label>
              <DataList.Value>
                <div className="flex gap-1">
                  <Badge size="1" variant="soft" color="gray">RT</Badge>
                  <Badge size="1" variant="soft" color="gray">GW</Badge>
                </div>
              </DataList.Value>
            </DataList.Item>
            <DataList.Item>
              <DataList.Label>City</DataList.Label>
              <DataList.Value>London</DataList.Value>
            </DataList.Item>
          </DataList.Root>
        </div>
      </Section>

      {/* ── Dialogs ────────────────────────────────────────────── */}
      <Section title="Dialog">
        <Dialog.Root>
          <Dialog.Trigger>
            <Button size="2" variant="outline">
              Open Dialog
            </Button>
          </Dialog.Trigger>
          <Dialog.Content maxWidth="480px">
            <Dialog.Title>Delete Property</Dialog.Title>
            <Dialog.Description size="2" color="gray">
              Are you sure you want to remove this property? This action cannot be undone.
            </Dialog.Description>
            <div className="mt-4 flex justify-end gap-3">
              <Dialog.Close>
                <Button variant="soft" color="gray">
                  Cancel
                </Button>
              </Dialog.Close>
              <Dialog.Close>
                <Button color="red">Delete</Button>
              </Dialog.Close>
            </div>
          </Dialog.Content>
        </Dialog.Root>
      </Section>

      {/* ── Dropdown Menu ──────────────────────────────────────── */}
      <Section title="Dropdown Menu">
        <DropdownMenu.Root>
          <DropdownMenu.Trigger>
            <Button variant="outline" size="2">
              Actions
              <CaretDown size={12} />
            </Button>
          </DropdownMenu.Trigger>
          <DropdownMenu.Content>
            <DropdownMenu.Item>
              <PencilSimple size={14} />
              Edit
            </DropdownMenu.Item>
            <DropdownMenu.Item>
              <Copy size={14} />
              Duplicate
            </DropdownMenu.Item>
            <DropdownMenu.Item>
              <Export size={14} />
              Export
            </DropdownMenu.Item>
            <DropdownMenu.Separator />
            <DropdownMenu.Item color="red">
              <Trash size={14} />
              Delete
            </DropdownMenu.Item>
          </DropdownMenu.Content>
        </DropdownMenu.Root>
      </Section>

      {/* ── Tooltips ───────────────────────────────────────────── */}
      <Section title="Tooltips">
        <div className="flex gap-4">
          <Tooltip content="This is a tooltip">
            <Button variant="soft" size="2">
              Hover me
            </Button>
          </Tooltip>
          <Tooltip content="Property ARN: 01234567890123456789">
            <Badge size="2" variant="outline">
              <Info size={12} />
              Hover for details
            </Badge>
          </Tooltip>
        </div>
      </Section>

      {/* ── Tabs ───────────────────────────────────────────────── */}
      <Section title="Tabs">
        <Tabs.Root defaultValue="tab1">
          <Tabs.List>
            <Tabs.Trigger value="tab1">Overview</Tabs.Trigger>
            <Tabs.Trigger value="tab2">Events</Tabs.Trigger>
            <Tabs.Trigger value="tab3">Configuration</Tabs.Trigger>
          </Tabs.List>
          <div className="pt-4">
            <Tabs.Content value="tab1">
              <Text size="2" color="gray">
                Overview tab content. This uses Radix Tabs with underline indicators.
              </Text>
            </Tabs.Content>
            <Tabs.Content value="tab2">
              <Text size="2" color="gray">Events tab content.</Text>
            </Tabs.Content>
            <Tabs.Content value="tab3">
              <Text size="2" color="gray">Configuration tab content.</Text>
            </Tabs.Content>
          </div>
        </Tabs.Root>
      </Section>

      {/* ── Empty State ────────────────────────────────────────── */}
      <Section title="Empty State">
        <div className="rounded-[var(--card-radius)] border border-[var(--gray-6)]">
          <EmptyState
            icon={<Buildings size={40} />}
            title="No properties found"
            description="Try adjusting your search or filters to find what you're looking for."
            action={{ label: "Clear filters", onClick: () => {} }}
          />
        </div>
      </Section>

      {/* ── Color Palette ──────────────────────────────────────── */}
      <Section title="Color Palette (Radix CSS Variables)">
        <div className="space-y-4">
          <div>
            <Text size="1" color="gray" weight="medium" className="mb-2 block">
              Accent scale (blue)
            </Text>
            <div className="flex gap-1">
              {Array.from({ length: 12 }, (_, i) => (
                <div
                  key={i}
                  className="flex h-10 w-10 items-center justify-center rounded-md text-[10px]"
                  style={{ backgroundColor: `var(--blue-${i + 1})`, color: i > 7 ? "white" : "var(--gray-12)" }}
                >
                  {i + 1}
                </div>
              ))}
            </div>
          </div>
          <div>
            <Text size="1" color="gray" weight="medium" className="mb-2 block">
              Gray scale (slate)
            </Text>
            <div className="flex gap-1">
              {Array.from({ length: 12 }, (_, i) => (
                <div
                  key={i}
                  className="flex h-10 w-10 items-center justify-center rounded-md text-[10px]"
                  style={{ backgroundColor: `var(--slate-${i + 1})`, color: i > 7 ? "white" : "var(--gray-12)" }}
                >
                  {i + 1}
                </div>
              ))}
            </div>
          </div>
          <div>
            <Text size="1" color="gray" weight="medium" className="mb-2 block">
              Semantic colors
            </Text>
            <div className="flex gap-2">
              {(["blue", "green", "red", "orange", "purple", "cyan", "indigo"] as const).map((c) => (
                <div key={c} className="text-center">
                  <div
                    className="mb-1 h-10 w-10 rounded-md"
                    style={{ backgroundColor: `var(--${c}-9)` }}
                  />
                  <Text size="1" color="gray">
                    {c}
                  </Text>
                </div>
              ))}
            </div>
          </div>
          <div>
            <Text size="1" color="gray" weight="medium" className="mb-2 block">
              Chart palette
            </Text>
            <div className="flex gap-2">
              {CHART_COLORS.primary.map((color, i) => (
                <div key={i} className="text-center">
                  <div
                    className="mb-1 h-10 w-16 rounded-md"
                    style={{ backgroundColor: color }}
                  />
                  <Text size="1" color="gray">
                    Series {i + 1}
                  </Text>
                </div>
              ))}
            </div>
          </div>
        </div>
      </Section>

      {/* ── Separators ─────────────────────────────────────────── */}
      <Section title="Separators">
        <div className="max-w-md space-y-4">
          <div>
            <Text size="1" color="gray" className="mb-2 block">
              Size 4 (full width)
            </Text>
            <Separator size="4" />
          </div>
          <div>
            <Text size="1" color="gray" className="mb-2 block">
              Size 2
            </Text>
            <Separator size="2" />
          </div>
        </div>
      </Section>

      {/* ── Theme Note ─────────────────────────────────────────── */}
      <Section title="Theme Configuration">
        <Callout.Root size="1">
          <Callout.Icon>
            <Info size={16} />
          </Callout.Icon>
          <Callout.Text>
            The entire color scheme is controlled by a single value in{" "}
            <Code>src/lib/theme.ts</Code>. Change{" "}
            <Code>accentColor: &quot;blue&quot;</Code> to any Radix color (indigo, green,
            purple, etc.) and every component updates automatically. Dark mode
            is one prop change on the Theme component.
          </Callout.Text>
        </Callout.Root>
      </Section>
    </div>
  );
}
