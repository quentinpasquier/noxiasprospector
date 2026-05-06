import { signOut } from "@/auth";
import { Button } from "@/components/ui/button";
import type { Me } from "@/lib/api";

/**
 * App header rendered inside the protected layout. Shows the user's avatar
 * (when Auth0 returned a `picture` claim) and a sign-out button wired as a
 * server action.
 */
export function AppHeader({ user }: { user: Me }): JSX.Element {
  const initials = (user.name ?? user.email)
    .split(/[\s.@]+/)
    .filter(Boolean)
    .slice(0, 2)
    .map((part) => part[0]?.toUpperCase() ?? "")
    .join("");

  return (
    <header className="flex h-14 items-center justify-between border-b bg-card px-6">
      <div className="font-semibold tracking-tight">NoxiasProspect</div>
      <div className="flex items-center gap-3">
        <div className="text-right text-sm leading-tight">
          <div className="font-medium">{user.name ?? user.email}</div>
          <div className="text-xs text-muted-foreground">{user.role}</div>
        </div>
        {user.picture_url ? (
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
        <form
          action={async () => {
            "use server";
            await signOut({ redirectTo: "/login" });
          }}
        >
          <Button type="submit" variant="ghost" size="sm">
            Déconnexion
          </Button>
        </form>
      </div>
    </header>
  );
}
