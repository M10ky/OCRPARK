"use client";

import { useContext } from "react";

import { AuthContext, type AuthContextValue } from "@/components/providers/AuthProvider";

/** Accès au contexte d'authentification (à utiliser dans un Client Component). */
export function useAuth(): AuthContextValue {
  const context = useContext(AuthContext);
  if (!context) {
    throw new Error("useAuth() doit être utilisé à l'intérieur de <AuthProvider>.");
  }
  return context;
}
