import { useParams, useNavigate } from "react-router-dom";
import { Text, Heading, Separator } from "@radix-ui/themes";
import { ArrowLeft } from "@phosphor-icons/react";

export function TransactionDetailPage() {
  const { rtId } = useParams<{ rtId: string }>();
  const navigate = useNavigate();

  return (
    <div className="flex flex-col gap-6">
      <button
        onClick={() => navigate(-1)}
        className="inline-flex items-center gap-1.5 text-[13px] font-medium text-[var(--gray-11)] hover:text-[var(--gray-12)]"
      >
        <ArrowLeft size={14} />
        Back to Transactions
      </button>

      <div>
        <Heading size="6" weight="medium">
          {rtId}
        </Heading>
        <Text as="p" size="2" color="gray" className="mt-1">
          Transaction detail page — will be wired to compiled data.
        </Text>
      </div>

      <Separator size="4" />

      <div className="rounded-[var(--card-radius)] border border-[var(--gray-6)] p-8 text-center">
        <Text size="2" color="gray">
          Transaction details, parties, addresses, and parcel information will be displayed here.
        </Text>
      </div>
    </div>
  );
}
