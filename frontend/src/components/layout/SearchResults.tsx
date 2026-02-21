import { useNavigate } from "react-router-dom";
import type { SearchResults as SearchResultsType } from "@/api/search";

interface Props {
  results: SearchResultsType;
  onClose: () => void;
}

const sections = [
  { key: "transactions" as const, label: "Transactions", path: "/transactions" },
  { key: "properties" as const, label: "Properties", path: "/properties" },
  { key: "parties" as const, label: "Parties", path: "/parties" },
  { key: "contacts" as const, label: "Contacts", path: "/contacts" },
] as const;

export default function SearchResults({ results, onClose }: Props) {
  const navigate = useNavigate();

  const hasResults = sections.some((s) => results[s.key].length > 0);

  if (!hasResults) {
    return (
      <div className="absolute top-[calc(100%+0.625rem)] left-0 z-[100] w-full p-3 rounded-4xl bg-b-surface2 border border-s-subtle shadow-dropdown">
        <div className="p-3 text-body-2 text-t-secondary">No results found</div>
      </div>
    );
  }

  return (
    <div className="absolute top-[calc(100%+0.625rem)] left-0 z-[100] w-full p-3 rounded-4xl bg-b-surface2 border border-s-subtle shadow-dropdown max-h-[420px] overflow-y-auto">
      {sections.map((section) => {
        const items = results[section.key];
        if (items.length === 0) return null;
        return (
          <div key={section.key}>
            <div className="p-3 text-body-2 text-t-secondary">
              {section.label}
            </div>
            {items.map((hit) => (
              <button
                key={hit.id}
                className="group relative flex w-full flex-col p-3 text-left cursor-pointer"
                onClick={() => {
                  navigate(`${section.path}/${hit.id}`);
                  onClose();
                }}
              >
                {/* Core 2 box-hover effect */}
                <div className="absolute inset-0 rounded-[20px] bg-gradient-to-b from-shade-09 to-[#ebebeb] before:absolute before:inset-[1.5px] before:bg-b-highlight before:rounded-[18.5px] before:border-[1.5px] before:border-b-surface2 invisible opacity-0 transition-all group-hover:visible group-hover:opacity-100" />
                <span className="relative z-[2] text-body-2 text-t-primary truncate w-full">
                  {hit.label}
                </span>
                <span className="relative z-[2] mt-0.5 text-caption text-t-secondary truncate w-full">
                  {hit.sublabel}
                </span>
              </button>
            ))}
          </div>
        );
      })}
    </div>
  );
}
