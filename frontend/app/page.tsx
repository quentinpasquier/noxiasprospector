import { redirect } from "next/navigation";

import { auth } from "@/auth";

/**
 * Root route — redirect to the dashboard for signed-in users, otherwise
 * to the public login page. NoxiasProspect is an internal tool, so there
 * is no public marketing surface here.
 */
export default async function HomePage(): Promise<never> {
  const session = await auth();
  redirect(session ? "/dashboard" : "/login");
}
