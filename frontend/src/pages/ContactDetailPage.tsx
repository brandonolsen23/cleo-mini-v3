import { useState, useEffect } from "react";
import { useParams, useNavigate } from "react-router-dom";
import { Text, Badge, Spinner } from "@radix-ui/themes";
import {
  ArrowLeft,
  Buildings,
  Phone,
  MapPin,
  Copy,
  Check,
} from "@phosphor-icons/react";
import { fetchApi } from "@/api/client";
import { formatCurrency, formatDate, formatStreet, titleCase } from "@/lib/utils";

interface GroupAssociation {
  group_id: string;
  group_name: string;
  group_display_name: string;
  status: "active" | "former";
  first_seen: string;
  first_seen_date: string;
  last_seen: string;
  last_seen_date: string;
  transaction_count: number;
  roles: string[];
}

interface ContactTransaction {
  property_id: string;
  address: string;
  city: string;
  sale_price: number | null;
  sale_date: string;
  rt_id: string;
  role: string;
  group_name: string;
}

interface ContactDetail {
  id: string;
  name: string;
  display_name: string | null;
  known_names: string[];
  all_names: string[];
  phones: string[];
  group_associations: GroupAssociation[];
  transactions: ContactTransaction[];
  transaction_count: number;
  cities: string[];
  total_value: number;
  latest_date: string;
  earliest_date: string;
  group_count: number;
}

function formatPhone(digits: string): string {
  if (digits.length === 10) {
    return `(${digits.slice(0, 3)}) ${digits.slice(3, 6)}-${digits.slice(6)}`;
  }
  return digits;
}

function CopyButton({ text }: { text: string }) {
  const [copied, setCopied] = useState(false);
  return (
    <button
      onClick={(e) => {
        e.stopPropagation();
        navigator.clipboard.writeText(text);
        setCopied(true);
        setTimeout(() => setCopied(false), 1500);
      }}
      className="ml-1 inline-flex text-[var(--gray-9)] hover:text-[var(--gray-11)]"
    >
      {copied ? <Check size={13} /> : <Copy size={13} />}
    </button>
  );
}

export function ContactDetailPage() {
  const { id } = useParams<{ id: string }>();
  const navigate = useNavigate();
  const [contact, setContact] = useState<ContactDetail | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  useEffect(() => {
    if (!id) return;
    setLoading(true);
    fetchApi<ContactDetail>(`/contacts/${id}`)
      .then(setContact)
      .catch((e) => setError(e.message))
      .finally(() => setLoading(false));
  }, [id]);

  if (loading) {
    return (
      <div className="flex items-center justify-center py-20">
        <Spinner size="3" />
      </div>
    );
  }

  if (error || !contact) {
    return (
      <div className="flex flex-col items-center justify-center py-20">
        <Text size="3" color="gray">
          {error || "Contact not found"}
        </Text>
        <button
          onClick={() => navigate("/contacts")}
          className="mt-4 text-[13px] font-medium text-[var(--accent-11)] hover:underline"
        >
          Back to Contacts
        </button>
      </div>
    );
  }

  const displayName = contact.display_name || contact.name;

  return (
    <div className="flex flex-col gap-6">
      {/* Back + header */}
      <div>
        <button
          onClick={() => navigate("/contacts")}
          className="mb-3 inline-flex items-center gap-1 text-[13px] font-medium text-[var(--gray-11)] hover:text-[var(--gray-12)]"
        >
          <ArrowLeft size={14} />
          Contacts
        </button>
        <div className="flex items-start justify-between">
          <div>
            <h2 className="text-[24px] font-medium leading-[32px] text-[var(--gray-12)]">
              {displayName}
            </h2>
            <Text size="2" color="gray">
              {contact.id}
            </Text>
          </div>
        </div>
      </div>

      {/* Stat row */}
      <div className="grid grid-cols-4 gap-4">
        <StatBox label="Transactions" value={contact.transaction_count} />
        <StatBox
          label="Total Volume"
          value={contact.total_value ? formatCurrency(contact.total_value) : "\u2014"}
          raw
        />
        <StatBox label="Groups" value={contact.group_count} />
        <StatBox label="Cities" value={contact.cities.length} />
      </div>

      <div className="grid grid-cols-2 gap-4">
        {/* Phones card */}
        <Card title="Phone Numbers" icon={<Phone size={15} />}>
          {contact.phones.length === 0 ? (
            <Text size="2" color="gray">No phones on record.</Text>
          ) : (
            <div className="flex flex-col gap-2">
              {contact.phones.map((p, i) => (
                <div key={i} className="flex items-center">
                  <Text size="2" className="block">
                    {formatPhone(p)}
                  </Text>
                  <CopyButton text={p} />
                </div>
              ))}
            </div>
          )}
        </Card>

        {/* Activity range */}
        <Card title="Activity Range" icon={<Buildings size={15} />}>
          <div className="flex flex-col gap-1">
            <div className="flex justify-between">
              <Text size="2" color="gray">First seen</Text>
              <Text size="2">{contact.earliest_date ? formatDate(contact.earliest_date) : "\u2014"}</Text>
            </div>
            <div className="flex justify-between">
              <Text size="2" color="gray">Last seen</Text>
              <Text size="2">{contact.latest_date ? formatDate(contact.latest_date) : "\u2014"}</Text>
            </div>
            <div className="flex justify-between">
              <Text size="2" color="gray">Total volume</Text>
              <Text size="2">{contact.total_value ? formatCurrency(contact.total_value) : "\u2014"}</Text>
            </div>
          </div>
        </Card>
      </div>

      {/* Group associations */}
      <Card title={`Group Associations (${contact.group_count})`} icon={<Buildings size={15} />} full>
        {contact.group_associations.length === 0 ? (
          <Text size="2" color="gray">No group associations.</Text>
        ) : (
          <table className="w-full text-[13px]">
            <thead>
              <tr className="border-b border-[var(--gray-4)] text-left text-[var(--gray-9)]">
                <th className="pb-2 font-medium">Group</th>
                <th className="pb-2 font-medium">Status</th>
                <th className="pb-2 font-medium">Role</th>
                <th className="pb-2 font-medium text-right">Txns</th>
                <th className="pb-2 font-medium text-right">First Seen</th>
                <th className="pb-2 font-medium text-right">Last Seen</th>
              </tr>
            </thead>
            <tbody>
              {contact.group_associations.map((a) => (
                <tr
                  key={a.group_id}
                  className="border-b border-[var(--gray-4)] last:border-0 cursor-pointer hover:bg-[var(--gray-2)]"
                  onClick={() => navigate(`/groups/${a.group_id}`)}
                >
                  <td className="py-2 pr-4 text-[var(--gray-12)]">
                    {a.group_display_name || a.group_name}
                  </td>
                  <td className="py-2 pr-4">
                    <Badge
                      size="1"
                      color={a.status === "active" ? "jade" : "gray"}
                      variant="soft"
                    >
                      {a.status}
                    </Badge>
                  </td>
                  <td className="py-2 pr-4 text-[var(--gray-11)]">
                    {a.roles.join(", ")}
                  </td>
                  <td className="py-2 pr-4 text-right text-[var(--gray-11)]">
                    {a.transaction_count}
                  </td>
                  <td className="py-2 pr-4 text-right text-[var(--gray-11)]">
                    {a.first_seen_date ? formatDate(a.first_seen_date) : "\u2014"}
                  </td>
                  <td className="py-2 text-right text-[var(--gray-11)]">
                    {a.last_seen_date ? formatDate(a.last_seen_date) : "\u2014"}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </Card>

      {/* Transaction history */}
      <Card title={`Transaction History (${contact.transaction_count})`} icon={<Buildings size={15} />} full>
        {contact.transactions.length === 0 ? (
          <Text size="2" color="gray">No transactions.</Text>
        ) : (
          <table className="w-full text-[13px]">
            <thead>
              <tr className="border-b border-[var(--gray-4)] text-left text-[var(--gray-9)]">
                <th className="pb-2 font-medium">Address</th>
                <th className="pb-2 font-medium">City</th>
                <th className="pb-2 font-medium">Role</th>
                <th className="pb-2 font-medium">Group</th>
                <th className="pb-2 font-medium text-right">Price</th>
                <th className="pb-2 font-medium text-right">Date</th>
              </tr>
            </thead>
            <tbody>
              {contact.transactions.map((t, i) => (
                <tr
                  key={`${t.rt_id}-${i}`}
                  className="border-b border-[var(--gray-4)] last:border-0 cursor-pointer hover:bg-[var(--gray-2)]"
                  onClick={() => navigate(`/properties/${t.property_id}`)}
                >
                  <td className="py-2 pr-4 text-[var(--gray-12)]">
                    {formatStreet(t.address)}
                  </td>
                  <td className="py-2 pr-4 text-[var(--gray-11)]">
                    {titleCase(t.city)}
                  </td>
                  <td className="py-2 pr-4">
                    <Badge
                      size="1"
                      color={t.role === "buyer" ? "blue" : "orange"}
                      variant="soft"
                    >
                      {t.role}
                    </Badge>
                  </td>
                  <td className="py-2 pr-4 text-[var(--gray-11)] max-w-[160px] truncate">
                    {t.group_name || "\u2014"}
                  </td>
                  <td className="py-2 pr-4 text-right text-[var(--gray-11)]">
                    {t.sale_price ? formatCurrency(t.sale_price) : "\u2014"}
                  </td>
                  <td className="py-2 text-right text-[var(--gray-11)]">
                    {t.sale_date ? formatDate(t.sale_date) : "\u2014"}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </Card>

      {/* Cities + known names */}
      <div className="grid grid-cols-2 gap-4">
        <Card title="Active Cities" icon={<MapPin size={15} />}>
          <div className="flex flex-wrap gap-1.5">
            {contact.cities.map((c) => (
              <Badge key={c} size="1" color="gray" variant="soft">
                {titleCase(c)}
              </Badge>
            ))}
          </div>
        </Card>
        {contact.all_names.length > 1 && (
          <Card title="Known Names" icon={<Buildings size={15} />}>
            <div className="flex flex-col gap-1">
              {contact.all_names.map((n, i) => (
                <Text key={i} size="2" className="block">
                  {n}
                </Text>
              ))}
            </div>
          </Card>
        )}
      </div>
    </div>
  );
}

/* ------------------------------------------------------------------ */
/* Shared sub-components                                                */
/* ------------------------------------------------------------------ */

function StatBox({
  label,
  value,
  raw,
}: {
  label: string;
  value: string | number;
  raw?: boolean;
}) {
  return (
    <div className="rounded-[var(--card-radius)] border border-[var(--gray-6)] p-5">
      <div className="text-[28px] font-medium leading-[36px] tracking-[-0.4px] text-[var(--gray-12)]">
        {raw ? value : typeof value === "number" ? value.toLocaleString() : value}
      </div>
      <div className="mt-1 text-[12px] font-medium text-[var(--gray-11)]">
        {label}
      </div>
    </div>
  );
}

function Card({
  title,
  icon,
  children,
  full,
}: {
  title: string;
  icon?: React.ReactNode;
  children: React.ReactNode;
  full?: boolean;
}) {
  return (
    <div
      className={`rounded-[var(--card-radius)] border border-[var(--gray-6)] ${full ? "" : ""}`}
    >
      <div className="flex items-center gap-2 border-b border-[var(--gray-4)] px-5 py-3">
        {icon && <span className="text-[var(--gray-9)]">{icon}</span>}
        <Text size="2" weight="medium">
          {title}
        </Text>
      </div>
      <div className="p-5">{children}</div>
    </div>
  );
}
