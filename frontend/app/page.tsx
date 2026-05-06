import { redirect } from "next/navigation";

import { AUTH_DISABLED, auth } from "@/auth";

/**
 * Root route — redirect to the dashboard for signed-in users, otherwise
 * to the public login page. NoxiasProspect is an internal tool, so there
 * is no public marketing surface here.
 *
 * In demo mode (`AUTH_DISABLED=true`) we always send the visitor straight
 * to `/dashboard`.
 */
export default async function HomePage(): Promise<never> {
  if (AUTH_DISABLED) {
    redirect("/dashboard");
  }
  const session = await auth();
  redirect(session ? "/dashboard" : "/login");
}
