import { AUTH_DISABLED, signOut } from "@/auth";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import type { Me } from "@/lib/api";

/**
 * App header rendered inside the protected layout. Shows the user's avatar
 * and a sign-out button (or a "Mode démo" badge when AUTH_DISABLED). Falls
 * back to a minimal header when `user` is null (backend cold-start).
 */
export function AppHeader({ user }: { user: Me | null }): JSX.Element {
  const initials = user
    ? (user.name ?? user.email)
        .split(/[\s.@]+/)
        .filter(Boolean)
        .slice(0, 2)
        .map((part) => part[0]?.toUpperCase() ?? "")
        .join("")
    : "??";

  const display = user?.name ?? user?.email ?? "Hors-ligne";
  const role = user?.role ?? "—";

  return (
    <header className="flex h-14 items-center justify-between border-b bg-card px-6">
      <div className="font-semibold tracking-tight">NoxiasProspect</div>
      <div className="flex items-center gap-3">
        <div className="text-right text-sm leading-tight">
          <div className="font-medium">{display}</div>
          <div className="text-xs text-muted-foreground">{role}</div>
        </div>
        {user?.picture_url ? (
          // eslint-disable-next-line @next/next/no-img-element
          <img
            src={user.picture_url}
            alt={user.name ?? user.email}
            className="h-8 w-8 rounded-full border"
          />
        ) : (
          <div className="flex h-8 w-8 items-center justify-center rounded-full bg-primary text-xs font-semibold text-primary-foreground">
            {initials || "?"}
          </div>
        )}
        {AUTH_DISABLED ? (
          <Badge variant="secondary" className="uppercase tracking-wide">
            Mode démo
          </Badge>
        ) : user ? (
          <form
            action={async () => {
              "use server";
              await signOut({ redirectTo: "/" });
            }}
          >
            <Button type="submit" variant="ghost" size="sm">
              Déconnexion
            </Button>
          </form>
        ) : null}
      </div>
    </header>
  );
}
