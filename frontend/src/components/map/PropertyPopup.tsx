import { Link } from "react-router-dom";
import type { PropertySummary } from "../../types/property";
import BrandBadge from "../shared/BrandBadge";
import MapLink from "../shared/MapLink";
import { Button } from "@/components/ui/button";

interface Props {
  property: PropertySummary;
  onClose: () => void;
}

export default function PropertyPopup({ property, onClose }: Props) {
  return (
    <div className="min-w-[220px] max-w-[280px]">
      {property.primary_photo && (
        <img
          src={property.primary_photo}
          alt={property.address}
          className="w-full h-32 object-cover rounded-md mb-2"
        />
      )}
      <div className="flex items-start justify-between gap-2 mb-1">
        <h3 className="text-sm font-semibold text-foreground leading-tight flex items-center gap-1.5">
          {property.address}
          <MapLink
            address={`${property.address}, ${property.city}`}
            lat={property.lat}
            lng={property.lng}
          />
        </h3>
        <button
          onClick={onClose}
          className="text-muted-foreground hover:text-foreground text-lg leading-none -mt-0.5"
        >
          &times;
        </button>
      </div>
      <p className="text-xs text-muted-foreground mb-2">{property.city}</p>

      <div className="space-y-1 text-xs text-foreground">
        <div className="flex justify-between">
          <span>Transactions</span>
          <span className="font-medium">{property.transaction_count}</span>
        </div>
        {property.latest_sale_price && (
          <div className="flex justify-between">
            <span>Latest price</span>
            <span className="font-medium">{property.latest_sale_price}</span>
          </div>
        )}
        {property.latest_sale_year && (
          <div className="flex justify-between">
            <span>Latest sale</span>
            <span className="font-medium">{property.latest_sale_year}</span>
          </div>
        )}
        {property.brands.length > 0 && (
          <div className="flex flex-wrap gap-1 pt-1">
            {property.brands.map((b) => (
              <BrandBadge key={b} brand={b} />
            ))}
          </div>
        )}
      </div>

      <Button variant="secondary" size="sm" className="mt-3 w-full text-xs" asChild>
        <Link to={`/properties/${property.prop_id}`}>
          View details
        </Link>
      </Button>
    </div>
  );
}
