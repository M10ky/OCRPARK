"use client";

import {
  createContext,
  useCallback,
  useEffect,
  useMemo,
  useState,
  type ReactNode,
} from "react";

import { api, setUnauthorizedHandler } from "@/lib/api";
import type { User } from "@/lib/types";

const TOKEN_KEY = "smpark.token";
const USER_KEY = "smpark.user";

export type AuthStatus = "loading" | "authenticated" | "anonymous";

export interface AuthContextValue {
  status: AuthStatus;
  token: string | null;
  user: User | null;
  login: (username: string, password: string) => Promise<void>;
  logout: () => void;
}

/** Contexte exporté pour `useAuth()` (le hook est le point d'entrée public). */
export const AuthContext = createContext<AuthContextValue | null>(null);

function readToken(): string | null {
  if (typeof window === "undefined") return null;
  return window.localStorage.getItem(TOKEN_KEY);
}

function readStoredUser(): User | null {
  if (typeof window === "undefined") return null;
  const raw = window.localStorage.getItem(USER_KEY);
  if (!raw) return null;
  try {
    return JSON.parse(raw) as User;
  } catch {
    return null;
  }
}

/**
 * Gestion de la session JWT.
 *
 * ⚠️ Le token est stocké dans `localStorage` : il est donc lisible par un
 * script de la page (risque XSS). La **sécurité réelle** est appliquée par le
 * backend (`get_current_user` sur chaque route) ; la protection des routes
 * côté Next.js reste un simple garde-fou d'interface.
 */
export function AuthProvider({ children }: { children: ReactNode }) {
  const [token, setToken] = useState<string | null>(null);
  const [user, setUser] = useState<User | null>(null);
  const [status, setStatus] = useState<AuthStatus>("loading");

  // Restauration de session au montage.
  useEffect(() => {
    const storedToken = readToken();
    if (!storedToken) {
      setStatus("anonymous");
      return;
    }
    setToken(storedToken);
    setUser(readStoredUser());

    let cancelled = false;
    api
      .me(storedToken)
      .then((profile) => {
        if (cancelled) return;
        setUser(profile);
        window.localStorage.setItem(USER_KEY, JSON.stringify(profile));
        setStatus("authenticated");
      })
      .catch(() => {
        if (cancelled) return;
        // Token invalide/expiré (backend redémarré avec une autre clé, etc.).
        window.localStorage.removeItem(TOKEN_KEY);
        window.localStorage.removeItem(USER_KEY);
        setToken(null);
        setUser(null);
        setStatus("anonymous");
      });

    return () => {
      cancelled = true;
    };
  }, []);

  const logout = useCallback(() => {
    if (typeof window !== "undefined") {
      window.localStorage.removeItem(TOKEN_KEY);
      window.localStorage.removeItem(USER_KEY);
    }
    setToken(null);
    setUser(null);
    setStatus("anonymous");
  }, []);

  // 401 sur n'importe quel appel => session expirée => purge + reconnexion.
  useEffect(() => {
    setUnauthorizedHandler(() => logout());
    return () => setUnauthorizedHandler(null);
  }, [logout]);

  const login = useCallback(async (username: string, password: string) => {
    const tokenResponse = await api.login(username, password);
    const profile = await api.me(tokenResponse.access_token);

    window.localStorage.setItem(TOKEN_KEY, tokenResponse.access_token);
    window.localStorage.setItem(USER_KEY, JSON.stringify(profile));

    setToken(tokenResponse.access_token);
    setUser(profile);
    setStatus("authenticated");
  }, []);

  const value = useMemo<AuthContextValue>(
    () => ({ status, token, user, login, logout }),
    [status, token, user, login, logout],
  );

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}
