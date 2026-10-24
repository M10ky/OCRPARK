"use client";

import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import type { ReactNode } from "react";

import { Badge } from "@/components/ui/Badge";
import { Button } from "@/components/ui/Button";
import { useAuth } from "@/hooks/useAuth";
import { PARKING_NAME } from "@/lib/config";

interface NavItem {
  href: string;
  label: string;
  /** false tant que la page correspondante n'est pas implémentée. */
  enabled: boolean;
}

const NAV_ITEMS: NavItem[] = [
  { href: "/dashboard", label: "Dashboard", enabled: true },
  { href: "/historique", label: "Historique", enabled: false },
  { href: "/plaques", label: "Plaques", enabled: false },
  { href: "/orchestration", label: "Orchestration", enabled: false },
];

/** Coquille applicative : navigation latérale + en-tête + zone de contenu. */
export function AppShell({ children }: { children: ReactNode }) {
  const { user, logout } = useAuth();
  const pathname = usePathname();
  const router = useRouter();

  function handleLogout() {
    logout();
    router.replace("/login");
  }

  return (
    <div className="flex min-h-screen">
      <aside className="hidden w-60 shrink-0 flex-col border-r border-border bg-surface md:flex">
        <div className="border-b border-border px-5 py-4">
          <p className="text-sm font-semibold tracking-tight text-foreground">{PARKING_NAME}</p>
          <p className="text-xs text-foreground/50">Supervision du parking</p>
        </div>
        <nav className="flex flex-1 flex-col gap-1 p-3">
          {NAV_ITEMS.map((item) => {
            const active = pathname === item.href || pathname.startsWith(`${item.href}/`);
            const base =
              "rounded-lg px-3 py-2 text-sm transition-colors flex items-center justify-between";
            const style = !item.enabled
              ? "text-foreground/35 cursor-not-allowed"
              : active
                ? "bg-brand/10 text-brand font-medium"
                : "text-foreground/70 hover:bg-surface-2 hover:text-foreground";

            if (!item.enabled) {
              return (
                <span key={item.href} className={`${base} ${style}`} title="Bientôt disponible">
                  {item.label}
                  <Badge tone="neutral">bientôt</Badge>
                </span>
              );
            }
            return (
              <Link key={item.href} href={item.href} className={`${base} ${style}`}>
                {item.label}
              </Link>
            );
          })}
        </nav>
      </aside>

      <div className="flex min-w-0 flex-1 flex-col">
        <header className="flex items-center justify-between gap-4 border-b border-border bg-surface px-5 py-3">
          <div className="flex items-center gap-3 md:hidden">
            <span className="text-sm font-semibold">{PARKING_NAME}</span>
          </div>
          <div className="ml-auto flex items-center gap-3">
            {user && (
              <>
                <span className="text-sm text-foreground/70">{user.username}</span>
                {user.is_admin && <Badge tone="brand">admin</Badge>}
              </>
            )}
            <Button variant="secondary" size="sm" onClick={handleLogout}>
              Déconnexion
            </Button>
          </div>
        </header>

        <main className="flex-1 overflow-x-auto p-5 md:p-6">{children}</main>
      </div>
    </div>
  );
}
