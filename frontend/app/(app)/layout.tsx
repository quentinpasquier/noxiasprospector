import { redirect } from "next/navigation";
import { Toaster } from "sonner";

import { AppHeader } from "@/components/app-header";
import { Sidebar } from "@/components/sidebar";
import { api } from "@/lib/api";

/**
 * Layout shared by every authenticated route. The middleware has already
 * gated access; here we resolve the current user via the backend `/auth/me`
 * (which upserts the user on first login) and render the header + sidebar.
 */
export default async function AppLayout({
  children,
}: {
  children: React.ReactNode;
}): Promise<JSX.Element> {
  let user;
  try {
    user = await api.me();
  } catch {
    redirect("/login");
  }

  return (
    <div className="flex min-h-screen">
      <Sidebar />
      <div className="flex min-w-0 flex-1 flex-col">
        <AppHeader user={user} />
        <main className="min-w-0 flex-1 bg-muted/30">{children}</main>
      </div>
      <Toaster richColors position="top-right" />
    </div>
  );
}
