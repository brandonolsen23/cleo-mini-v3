import { useLocation } from "react-router-dom";
import { Separator } from "@radix-ui/themes";
import { MagnifyingGlassIcon, QuestionMarkCircledIcon } from "@radix-ui/react-icons";

/** Map route paths to page titles for breadcrumb display */
const ROUTE_TITLES: Record<string, string> = {
  "/dashboard": "Dashboard",
  "/properties": "Properties",
  "/groups": "Groups",
  "/transactions": "Transactions",
  "/trace": "Trace",
  "/monitor": "Monitor",
  "/map": "Map",
  "/admin": "Admin",
  "/showcase": "Design System",
};

export function Header() {
  const location = useLocation();

  // Determine current page title from route
  const pathBase = "/" + location.pathname.split("/").filter(Boolean)[0];
  const pageTitle = ROUTE_TITLES[pathBase] ?? "";

  return (
    <header className="app-header flex items-center justify-between border-b border-[var(--gray-4)] bg-[var(--gray-1)] px-5">
      {/* Left: team name + separator + page context */}
      <div className="flex items-center gap-4" style={{ height: "100%" }}>
        <h1
          className="text-[var(--gray-12)]"
          style={{ fontSize: "var(--font-size-2)", fontWeight: 500, lineHeight: "var(--line-height-2)", whiteSpace: "nowrap" }}
        >
          Cleo
        </h1>
        <Separator orientation="vertical" size="1" />
        <span
          className="text-[var(--gray-11)]"
          style={{ fontSize: "var(--font-size-2)", fontWeight: 300, whiteSpace: "nowrap" }}
        >
          {pageTitle}
        </span>
      </div>

      {/* Right: search + help + avatar */}
      <div className="flex items-center gap-1" style={{ height: "100%" }}>
        {/* Search button (Cmd+K style) */}
        <button
          className="flex items-center gap-2 rounded-[var(--radius-2)] px-2.5 py-1.5 text-[var(--gray-11)] transition-colors hover:bg-[var(--gray-a3)]"
          onClick={() => {}}
        >
          <MagnifyingGlassIcon width={15} height={15} />
          <span style={{ fontSize: "var(--font-size-2)" }}>Search</span>
          <kbd className="ml-1 rounded border border-[var(--gray-6)] px-1.5 py-0.5 text-[11px] leading-none text-[var(--gray-9)]">
            <span style={{ fontSize: 11 }}>&#8984;K</span>
          </kbd>
        </button>

        {/* Help button */}
        <button className="flex items-center gap-1.5 rounded-[var(--radius-2)] px-2.5 py-1.5 text-[var(--gray-11)] transition-colors hover:bg-[var(--gray-a3)]">
          <QuestionMarkCircledIcon width={15} height={15} />
        </button>

        {/* User avatar */}
        <button className="ml-2 flex h-7 w-7 items-center justify-center rounded-full bg-[var(--gray-3)] text-[11px] font-medium text-[var(--gray-11)] transition-colors hover:bg-[var(--gray-4)]">
          B
        </button>
      </div>
    </header>
  );
}
