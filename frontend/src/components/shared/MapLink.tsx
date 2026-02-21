import { ArrowSquareOut } from "@phosphor-icons/react";

interface MapLinkProps {
  address: string;
  lat?: number | null;
  lng?: number | null;
  size?: number;
}

export default function MapLink({ address, lat, lng, size = 12 }: MapLinkProps) {
  const query =
    lat != null && lng != null
      ? `${lat},${lng}`
      : encodeURIComponent(address);
  const url = `https://www.google.com/maps/search/?api=1&query=${query}`;

  return (
    <a
      href={url}
      target="_blank"
      rel="noopener noreferrer"
      title="Open in Google Maps"
      className="inline-flex items-center text-muted-foreground hover:text-foreground transition-colors shrink-0"
      onClick={(e) => e.stopPropagation()}
    >
      <ArrowSquareOut size={size} />
    </a>
  );
}
