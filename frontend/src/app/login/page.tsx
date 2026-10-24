"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";

import { Button } from "@/components/ui/Button";
import { Input } from "@/components/ui/Input";
import { useAuth } from "@/hooks/useAuth";
import { PARKING_NAME } from "@/lib/config";

/**
 * N'accepte qu'une redirection interne (évite l'open redirect).
 * Le paramètre `next` est lu au moment de la soumission (côté client) et non
 * via `useSearchParams` : la page reste ainsi prérendue statiquement, donc le
 * formulaire est visible même avant l'exécution de JavaScript.
 */
function safeNext(candidate: string | null): string {
  if (!candidate) return "/dashboard";
  if (!candidate.startsWith("/") || candidate.startsWith("//")) return "/dashboard";
  return candidate;
}

export default function LoginPage() {
  const router = useRouter();
  const { login } = useAuth();

  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [pending, setPending] = useState(false);

  async function handleSubmit(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setError(null);
    setPending(true);
    try {
      await login(username, password);
      const next = new URLSearchParams(window.location.search).get("next");
      router.replace(safeNext(next));
    } catch (err) {
      setError(err instanceof Error ? err.message : "Erreur inattendue.");
    } finally {
      setPending(false);
    }
  }

  return (
    <main className="flex min-h-screen items-center justify-center bg-background p-6">
      <div className="w-full max-w-sm">
        <div className="mb-6 text-center">
          <h1 className="text-xl font-semibold tracking-tight">{PARKING_NAME}</h1>
          <p className="mt-1 text-sm text-foreground/60">Connexion à la supervision</p>
        </div>

        <form
          onSubmit={handleSubmit}
          className="flex flex-col gap-4 rounded-xl border border-border bg-surface p-6 shadow-sm"
        >
          <Input
            label="Identifiant"
            name="username"
            autoComplete="username"
            value={username}
            onChange={(event) => setUsername(event.target.value)}
            placeholder="admin"
            required
            disabled={pending}
          />
          <Input
            label="Mot de passe"
            name="password"
            type="password"
            autoComplete="current-password"
            value={password}
            onChange={(event) => setPassword(event.target.value)}
            required
            disabled={pending}
          />

          {error && (
            <p role="alert" className="rounded-lg bg-danger/10 px-3 py-2 text-sm text-danger">
              {error}
            </p>
          )}

          <Button type="submit" disabled={pending}>
            {pending ? "Connexion…" : "Se connecter"}
          </Button>
        </form>
      </div>
    </main>
  );
}
