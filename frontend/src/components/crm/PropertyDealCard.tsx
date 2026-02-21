import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { Plus } from "@phosphor-icons/react";
import { usePropertyDeals, createDeal } from "../../api/crm";
import DealStageBadge from "./DealStageBadge";
import DealForm from "./DealForm";
import { Card, CardHeader, CardTitle, CardContent } from "@/components/ui/card";
import { Button } from "@/components/ui/button";

interface Props {
  propId: string;
  address: string;
  city: string;
}

export default function PropertyDealCard({ propId, address }: Props) {
  const { data: deals, loading, reload } = usePropertyDeals(propId);
  const navigate = useNavigate();
  const [showForm, setShowForm] = useState(false);

  // Only show active deals (not closed)
  const activeDeals = deals.filter(
    (d) => d.stage !== "closed_won" && d.stage !== "closed_lost",
  );
  const closedDeals = deals.filter(
    (d) => d.stage === "closed_won" || d.stage === "closed_lost",
  );

  if (loading) return null;
  if (deals.length === 0 && !showForm) {
    return (
      <Card>
        <CardHeader className="px-5 py-3 border-b border-border flex-row items-center justify-between">
          <CardTitle className="text-sm font-semibold uppercase tracking-wider">
            Deals
          </CardTitle>
          <Button
            variant="ghost"
            size="sm"
            onClick={() => setShowForm(true)}
            className="h-auto px-2 py-1 text-xs"
          >
            <Plus size={12} />
            Create Deal
          </Button>
        </CardHeader>
        <CardContent className="px-5 py-4">
          <p className="text-sm text-muted-foreground">No deals for this property.</p>
        </CardContent>
      </Card>
    );
  }

  return (
    <Card>
      <CardHeader className="px-5 py-3 border-b border-border flex-row items-center justify-between">
        <CardTitle className="text-sm font-semibold uppercase tracking-wider">
          Deals ({deals.length})
        </CardTitle>
        <Button
          variant="ghost"
          size="sm"
          onClick={() => setShowForm(true)}
          className="h-auto px-2 py-1 text-xs"
        >
          <Plus size={12} />
          New Deal
        </Button>
      </CardHeader>
      <CardContent className="px-5 py-4">
        {showForm && (
          <div className="mb-4 pb-4 border-b border-border">
            <DealForm
              initial={{ prop_id: propId, title: `${address} Deal` }}
              onSubmit={async (formData) => {
                const result = await createDeal(formData);
                setShowForm(false);
                reload();
                navigate(`/crm/deals/${result.deal_id}`);
              }}
              onCancel={() => setShowForm(false)}
              submitLabel="Create Deal"
            />
          </div>
        )}

        {activeDeals.length > 0 && (
          <table className="w-full">
            <thead>
              <tr className="border-b border-border">
                <th className="text-left text-[10px] font-medium text-muted-foreground uppercase py-2 pr-4">Title</th>
                <th className="text-left text-[10px] font-medium text-muted-foreground uppercase py-2 pr-4">Stage</th>
                <th className="text-left text-[10px] font-medium text-muted-foreground uppercase py-2 pr-4">Contacts</th>
                <th className="text-left text-[10px] font-medium text-muted-foreground uppercase py-2">Updated</th>
              </tr>
            </thead>
            <tbody>
              {activeDeals.map((deal) => (
                <tr
                  key={deal.deal_id}
                  className="border-b border-border hover:bg-accent cursor-pointer transition-colors"
                  onClick={() => navigate(`/crm/deals/${deal.deal_id}`)}
                >
                  <td className="py-3 pr-4 text-sm font-medium">{deal.title}</td>
                  <td className="py-3 pr-4"><DealStageBadge stage={deal.stage} /></td>
                  <td className="py-3 pr-4 text-xs text-muted-foreground">
                    {deal.contacts.map((c) => c.name).join(", ") || "\u2014"}
                  </td>
                  <td className="py-3 text-xs">{deal.updated?.slice(0, 10)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        )}

        {closedDeals.length > 0 && (
          <div className={activeDeals.length > 0 ? "mt-4 pt-3 border-t border-border" : ""}>
            <p className="text-xs text-muted-foreground font-medium mb-2">
              Closed ({closedDeals.length})
            </p>
            {closedDeals.map((deal) => (
              <div
                key={deal.deal_id}
                className="flex items-center gap-3 py-1.5 cursor-pointer hover:bg-accent rounded px-1 -mx-1 transition-colors"
                onClick={() => navigate(`/crm/deals/${deal.deal_id}`)}
              >
                <DealStageBadge stage={deal.stage} />
                <span className="text-sm text-muted-foreground">{deal.title}</span>
              </div>
            ))}
          </div>
        )}
      </CardContent>
    </Card>
  );
}
