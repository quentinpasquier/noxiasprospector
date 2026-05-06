import Link from "next/link";

import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { api } from "@/lib/api";

export default async function DashboardPage(): Promise<JSX.Element> {
  const me = await api.me();

  return (
    <div className="container py-10">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-3xl font-bold tracking-tight">Tableau de bord</h1>
          <p className="mt-1 text-sm text-muted-foreground">
            Bienvenue, {me.name ?? me.email}.
          </p>
        </div>
        <Button asChild size="lg">
          <Link href="/searches/new">+ Nouvelle recherche</Link>
        </Button>
      </div>

      <div className="mt-8 grid gap-4 md:grid-cols-3">
        <Card>
          <CardHeader>
            <CardTitle>Compte</CardTitle>
          </CardHeader>
          <CardContent className="space-y-1 text-sm">
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
          </CardContent>
        </Card>
        <Card>
          <CardHeader>
            <CardTitle>Démarrer</CardTitle>
          </CardHeader>
          <CardContent className="text-sm text-muted-foreground">
            Lance une nouvelle prospection en sélectionnant des communes
            d&apos;Auvergne-Rhône-Alpes et un mot-clé métier.
          </CardContent>
        </Card>
        <Card>
          <CardHeader>
            <CardTitle>Exports Pipedrive</CardTitle>
          </CardHeader>
          <CardContent className="text-sm text-muted-foreground">
            Phase 5 — bientôt disponible.
          </CardContent>
        </Card>
      </div>
    </div>
  );
}
