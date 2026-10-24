"use client";

import { useContext } from "react";

import {
  LiveContext,
  type LiveContextValue,
} from "@/components/providers/LiveProvider";

/** Accès à l'état temps réel (à utiliser dans un Client Component). */
export function useLive(): LiveContextValue {
  const context = useContext(LiveContext);
  if (!context) {
    throw new Error("useLive() doit être utilisé à l'intérieur de <LiveProvider>.");
  }
  return context;
}
