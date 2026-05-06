"use client";

import { Crosshair, ListChecks, ShieldOff } from "lucide-react";
import Link from "next/link";
import { usePathname } from "next/navigation";

import { cn } from "@/lib/utils";

type NavItem = {
  href: string;
  label: string;
  icon: React.ElementType;
};

const NAV_ITEMS: NavItem[] = [
  { href: "/cibler", label: "Cibler", icon: Crosshair },
  { href: "/searches", label: "Recherches", icon: ListChecks },
  { href: "/blacklist", label: "Blacklist", icon: ShieldOff },
];

export function Sidebar(): JSX.Element {
  const pathname = usePathname();
  return (
    <aside className="hidden w-56 shrink-0 border-r bg-card md:flex md:flex-col">
      <div className="border-b px-6 py-4">
        <Link href="/cibler" className="text-base font-bold tracking-tight">
          NoxiasProspect
        </Link>
      </div>
      <nav className="flex-1 space-y-1 p-3">
        {NAV_ITEMS.map((item) => {
          const Icon = item.icon;
          const active =
            pathname === item.href ||
            (item.href !== "/cibler" && pathname?.startsWith(item.href));
          return (
            <Link
              key={item.href}
              href={item.href}
              className={cn(
                "flex items-center gap-3 rounded-md px-3 py-2 text-sm transition-colors",
                active
                  ? "bg-primary/10 text-primary font-medium"
                  : "text-muted-foreground hover:bg-accent hover:text-accent-foreground",
              )}
            >
              <Icon className="h-4 w-4" />
              {item.label}
            </Link>
          );
        })}
      </nav>
      <div className="border-t p-3 text-xs text-muted-foreground">
        Cibler → Enrichir → Exporter Pipedrive
      </div>
    </aside>
  );
}
