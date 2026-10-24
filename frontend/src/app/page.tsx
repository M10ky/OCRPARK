import { redirect } from "next/navigation";

/** Racine : redirige vers le dashboard (lui-même protégé par RequireAuth). */
export default function Home() {
  redirect("/dashboard");
}
