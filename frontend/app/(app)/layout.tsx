import { Toaster } from "sonner";

import { AppHeader } from "@/components/app-header";
import { Sidebar } from "@/components/sidebar";
import { ApiError, type Me, api } from "@/lib/api";

/**
 * Layout shared by every protected route. With AUTH_DISABLED=true the
 * backend resolves every request to a single demo@noxias.fr user, so
 * `api.me()` always succeeds. The fallback handles the case where the
 * backend is not yet reachable (cold start) and shows a degraded shell
 * instead of an opaque error page.
 */
export default async function AppLayout({
  children,
}: {
  children: React.ReactNode;
}): Promise<JSX.Element> {
  let user: Me | null = null;
  let backendError: string | null = null;
  try {
    user = await api.me();
  } catch (e) {
    backendError = e instanceof ApiError ? e.message : "Backend injoignable.";
  }

  return (
    <div className="flex min-h-screen">
      <Sidebar />
      <div className="flex min-w-0 flex-1 flex-col">
        <AppHeader user={user} />
        {backendError ? (
          <div className="border-b bg-destructive/10 px-6 py-2 text-xs text-destructive">
            Backend injoignable ({backendError}). Les recherches ne seront pas
            sauvegardées tant que la connexion n&apos;est pas rétablie.
          </div>
        ) : null}
        <main className="min-w-0 flex-1 bg-muted/30">{children}</main>
      </div>
      <Toaster richColors position="top-right" />
    </div>
  );
}
