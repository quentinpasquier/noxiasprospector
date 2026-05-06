import { Button } from "@/components/ui/button";
import { signIn } from "@/auth";

type LoginPageProps = {
  searchParams: Promise<{ callbackUrl?: string; error?: string }>;
};

/**
 * Public login screen. The button triggers the Auth0 sign-in flow via a
 * server action — Auth0 then handles Google as a social connection.
 */
export default async function LoginPage({
  searchParams,
}: LoginPageProps): Promise<JSX.Element> {
  const { callbackUrl, error } = await searchParams;

  return (
    <main className="flex min-h-screen items-center justify-center bg-background px-4">
      <div className="w-full max-w-sm rounded-xl border bg-card p-8 shadow-sm">
        <h1 className="text-center text-2xl font-bold tracking-tight">NoxiasProspect</h1>
        <p className="mt-2 text-center text-sm text-muted-foreground">
          Connecte-toi avec ton compte Google Noxias.
        </p>

        {error ? (
          <p className="mt-6 rounded-md bg-destructive/10 px-4 py-2 text-sm text-destructive">
            La connexion a échoué. Réessaie ou contacte l&apos;équipe tech.
          </p>
        ) : null}

        <form
          action={async () => {
            "use server";
            await signIn("auth0", {
              redirectTo: callbackUrl ?? "/dashboard",
            });
          }}
          className="mt-6"
        >
          <Button type="submit" className="w-full" size="lg">
            Se connecter avec Google
          </Button>
        </form>

        <p className="mt-6 text-center text-xs text-muted-foreground">
          L&apos;accès est réservé à l&apos;équipe Noxias.
        </p>
      </div>
    </main>
  );
}
