"use client";

import type { ReactNode } from "react";

import { RequireAuth } from "@/components/layout/RequireAuth";
import { AppShell } from "@/components/layout/AppShell";
import { LiveProvider } from "@/components/providers/LiveProvider";

/** Layout des pages authentifiées : garde de session + coquille applicative. */
export default function AppLayout({ children }: { children: ReactNode }) {
  return (
    <RequireAuth>
      <LiveProvider>
        <AppShell>{children}</AppShell>
      </LiveProvider>
    </RequireAuth>
  );
}
