import { AppHeader } from "@/components/app-header";
import { api } from "@/lib/api";
import { redirect } from "next/navigation";

/**
 * Layout shared by all authenticated app sections. The middleware has already
 * gated access; here we resolve the current user via the backend `/auth/me`
 * (which upserts the user on first login) and render the header.
 */
export default async function ProtectedLayout({
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
    <div className="flex min-h-screen flex-col">
      <AppHeader user={user} />
      <div className="flex-1">{children}</div>
    </div>
  );
}
