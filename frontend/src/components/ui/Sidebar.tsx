import { NavLink, useLocation } from "react-router-dom";
import { Separator } from "@radix-ui/themes";
import {
  DashboardIcon,
  HomeIcon,
  FileTextIcon,
  MixerVerticalIcon,
  ActivityLogIcon,
  GlobeIcon,
  GearIcon,
  PersonIcon,
  IdCardIcon,
  RocketIcon,
  ListBulletIcon,
} from "@radix-ui/react-icons";

interface NavItem {
  label: string;
  href: string;
  icon: React.ElementType;
}

interface NavGroup {
  heading?: string;
  items: NavItem[];
}

const NAV_GROUPS: NavGroup[] = [
  {
    items: [
      { label: "Overview", href: "/dashboard", icon: DashboardIcon },
      { label: "Properties", href: "/properties", icon: HomeIcon },
      { label: "Groups", href: "/groups", icon: PersonIcon },
      { label: "Contacts", href: "/contacts", icon: IdCardIcon },
      { label: "Transactions", href: "/transactions", icon: FileTextIcon },
      { label: "Map", href: "/map", icon: GlobeIcon },
    ],
  },
  {
    heading: "CRM",
    items: [
      { label: "Deals", href: "/deals", icon: RocketIcon },
      { label: "Lists", href: "/lists", icon: ListBulletIcon },
    ],
  },
  {
    heading: "Tools",
    items: [
      { label: "Trace", href: "/trace", icon: MixerVerticalIcon },
      { label: "Monitor", href: "/monitor", icon: ActivityLogIcon },
    ],
  },
];

const FOOTER_ITEMS: NavItem[] = [
  { label: "Settings", href: "/admin", icon: GearIcon },
];

function NavItemLink({ item, active }: { item: NavItem; active: boolean }) {
  return (
    <NavLink
      to={item.href}
      style={{
        display: "flex",
        alignItems: "center",
        gap: 8,
        height: 36,
        padding: "0 9px",
        borderRadius: "var(--radius-2)",
        fontSize: "var(--font-size-2)",
        fontWeight: active ? 500 : 400,
        lineHeight: 1,
        color: active
          ? "var(--nav-text-active)"
          : "var(--nav-text-inactive)",
        background: active ? "var(--nav-active-bg)" : "transparent",
        whiteSpace: "nowrap",
        userSelect: "none",
        transition: "background 80ms ease-out, color 80ms ease-out",
      }}
      onMouseEnter={(e) => {
        if (!active) e.currentTarget.style.background = "var(--nav-hover-bg)";
      }}
      onMouseLeave={(e) => {
        if (!active) e.currentTarget.style.background = "transparent";
      }}
    >
      <item.icon
        width={18}
        height={18}
        style={{
          color: active
            ? "var(--nav-icon-active)"
            : "var(--nav-icon-inactive)",
          flexShrink: 0,
        }}
      />
      {item.label}
    </NavLink>
  );
}

export function Sidebar() {
  const location = useLocation();

  function isActive(href: string) {
    return (
      location.pathname === href ||
      (href !== "/dashboard" && location.pathname.startsWith(href))
    );
  }

  return (
    <nav
      aria-label="app"
      className="app-sidebar flex flex-col border-r border-[var(--gray-4)] bg-[var(--gray-2)]"
    >
      {/* Logo area — matches WorkOS 56px header row */}
      <div
        className="flex items-center px-5"
        style={{ height: "var(--header-height)" }}
      >
        <img
          src={import.meta.env.BASE_URL + "cleo-logo-grey.png"}
          alt="Cleo"
          style={{ height: 22 }}
          draggable={false}
        />
      </div>

      {/* Scrollable nav area */}
      <div className="flex flex-1 flex-col justify-between overflow-y-auto">
        {/* Menu groups */}
        <div className="flex flex-col gap-0.5 p-3 pb-6">
          {NAV_GROUPS.map((group, gi) => (
            <div key={gi}>
              {/* Group heading */}
              {group.heading && (
                <div className="flex items-center gap-2 py-1" style={{ height: 32 }}>
                  <span
                    className="shrink-0 text-[var(--gray-9)]"
                    style={{ fontSize: 12, fontWeight: 500 }}
                  >
                    {group.heading}
                  </span>
                  <Separator orientation="horizontal" size="4" />
                </div>
              )}

              {/* Nav items */}
              <div className="flex flex-col gap-px">
                {group.items.map((item) => (
                  <NavItemLink
                    key={item.href}
                    item={item}
                    active={isActive(item.href)}
                  />
                ))}
              </div>
            </div>
          ))}
        </div>

        {/* Footer: separator + settings */}
        <div className="flex flex-col gap-2 p-3 pt-0">
          <Separator orientation="horizontal" size="4" />
          <div className="flex flex-col gap-px">
            {FOOTER_ITEMS.map((item) => (
              <NavItemLink
                key={item.href}
                item={item}
                active={isActive(item.href)}
              />
            ))}
          </div>
        </div>
      </div>
    </nav>
  );
}
