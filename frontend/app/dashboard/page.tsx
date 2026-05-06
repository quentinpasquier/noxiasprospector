import { Card } from "@/components/ui/card";
import { api } from "@/lib/api";

export default async function DashboardPage(): Promise<JSX.Element> {
  const me = await api.me();

  return (
    <main className="container py-10">
      <h1 className="text-3xl font-bold tracking-tight">Tableau de bord</h1>
      <p className="mt-2 text-muted-foreground">
        Bienvenue, {me.name ?? me.email}.
      </p>

      <Card className="mt-8 max-w-md">
        <div className="space-y-2 p-6 text-sm">
          <div>
            <span className="text-muted-foreground">Email :</span>{" "}
            <span className="font-medium">{me.email}</span>
          </div>
          <div>
            <span className="text-muted-foreground">Rôle :</span>{" "}
            <span className="font-medium">{me.role}</span>
          </div>
          <div>
            <span className="text-muted-foreground">Dernière connexion :</span>{" "}
            <span className="font-medium">
              {me.last_login_at
                ? new Date(me.last_login_at).toLocaleString("fr-FR")
                : "—"}
            </span>
          </div>
        </div>
      </Card>

      <p className="mt-10 text-sm text-muted-foreground">
        Phase 2 — auth Auth0 opérationnelle. Recherches en Phase 3.
      </p>
    </main>
  );
}
