import { NavLink } from "react-router-dom";
import { Receipt, Buildings, Users, UserCircle, Storefront, MapPin, SquaresFour, Palette, GearSix, AddressBook, Handshake } from "@phosphor-icons/react";
import { cn } from "@/lib/utils";
import type { Icon } from "@phosphor-icons/react";

type NavItem = { to: string; label: string; icon: Icon };
type NavGroup = { label: string; items: NavItem[] };

const navGroups: NavGroup[] = [
  {
    label: "",
    items: [
      { to: "/dashboard", label: "Dashboard", icon: SquaresFour },
      { to: "/transactions", label: "Transactions", icon: Receipt },
      { to: "/properties", label: "Properties", icon: Buildings },
      { to: "/parties", label: "Parties", icon: Users },
      { to: "/contacts", label: "Contacts", icon: UserCircle },
      { to: "/brands", label: "Brands", icon: Storefront },
      { to: "/map", label: "Map", icon: MapPin },
    ],
  },
  {
    label: "CRM",
    items: [
      { to: "/crm/contacts", label: "CRM Contacts", icon: AddressBook },
      { to: "/crm/deals", label: "Deals", icon: Handshake },
    ],
  },
  {
    label: "",
    items: [
      { to: "/components", label: "Components", icon: Palette },
      { to: "/admin", label: "Admin", icon: GearSix },
    ],
  },
];

function NavItem({ item }: { item: NavItem }) {
  return (
    <NavLink
      to={item.to}
      className={({ isActive }) =>
        cn(
          "flex items-center gap-3 px-3 py-2.5 text-body-1 font-medium transition-colors rounded-xl",
          isActive
            ? "bg-b-surface2 text-foreground shadow-widget"
            : "text-t-secondary hover:text-foreground"
        )
      }
    >
      <item.icon size={20} />
      {item.label}
    </NavLink>
  );
}

export default function Sidebar() {
  return (
    <aside className="fixed left-0 top-0 bottom-0 w-60 bg-b-surface1 flex flex-col">
      <div className="h-16 flex items-center px-6">
        <span className="text-h5 font-semibold">
          Cleo
        </span>
      </div>
      <nav className="flex-1 px-3 py-2">
        {navGroups.map((group, gi) => (
          <div key={gi} className={gi > 0 ? "mt-4" : ""}>
            {group.label && (
              <div className="px-3 py-1.5 text-[10px] font-semibold uppercase tracking-widest text-t-secondary">
                {group.label}
              </div>
            )}
            <div className="space-y-0.5">
              {group.items.map((item) => (
                <NavItem key={item.to} item={item} />
              ))}
            </div>
          </div>
        ))}
      </nav>
    </aside>
  );
}
