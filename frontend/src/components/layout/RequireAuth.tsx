"use client";

import { useEffect, type ReactNode } from "react";
import { usePathname, useRouter } from "next/navigation";

import { useAuth } from "@/hooks/useAuth";

function FullPageMessage({ label }: { label: string }) {
  return (
    <div className="flex min-h-screen items-center justify-center bg-background">
      <div className="flex items-center gap-3 text-sm text-foreground/60">
        <span className="h-3 w-3 animate-pulse rounded-full bg-brand" />
        {label}
      </div>
    </div>
  );
}

/**
 * Garde de routes authentifiées.
 *
 * ⚠️ Protection d'INTERFACE uniquement : le token vit dans `localStorage`, il
 * n'est donc pas accessible au middleware Next.js (côté serveur). La
 * véritable barrière de sécurité reste le backend, qui refuse toute route
 * métier sans JWT valide.
 */
export function RequireAuth({ children }: { children: ReactNode }) {
  const { status } = useAuth();
  const router = useRouter();
  const pathname = usePathname();

  useEffect(() => {
    if (status === "anonymous") {
      router.replace(`/login?next=${encodeURIComponent(pathname)}`);
    }
  }, [status, router, pathname]);

  if (status !== "authenticated") {
    return (
      <FullPageMessage
        label={status === "loading" ? "Vérification de la session…" : "Redirection…"}
      />
    );
  }
  return <>{children}</>;
}
