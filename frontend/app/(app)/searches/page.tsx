import Link from "next/link";

import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { api } from "@/lib/api";
import type { SearchStatus } from "@/lib/api";

const STATUS_LABELS: Record<SearchStatus, string> = {
  pending: "En attente",
  running: "En cours",
  completed: "Terminée",
  failed: "Échec",
};

const STATUS_COLOR: Record<SearchStatus, string> = {
  pending: "bg-muted text-muted-foreground",
  running: "bg-score-cold/15 text-score-cold",
  completed: "bg-score-warm/15 text-score-warm",
  failed: "bg-destructive/15 text-destructive",
};

export default async function SearchesPage(): Promise<JSX.Element> {
  const searches = await api.listSearches();

  return (
    <div className="container py-10">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-3xl font-bold tracking-tight">Recherches</h1>
          <p className="mt-1 text-sm text-muted-foreground">
            {searches.length} recherche(s) au total.
          </p>
        </div>
        <Button asChild>
          <Link href="/searches/new">+ Nouvelle recherche</Link>
        </Button>
      </div>

      <div className="mt-8 space-y-3">
        {searches.length === 0 ? (
          <Card className="p-8 text-center text-sm text-muted-foreground">
            Pas encore de recherche. Lance ta première prospection en cliquant sur
            « Nouvelle recherche ».
          </Card>
        ) : (
          searches.map((s) => (
            <Link
              key={s.id}
              href={`/searches/${s.id}`}
              className="block rounded-lg border bg-card p-4 transition-colors hover:bg-accent/50"
            >
              <div className="flex items-start justify-between gap-3">
                <div className="min-w-0">
                  <div className="truncate text-base font-semibold">{s.query}</div>
                  <div className="mt-1 text-xs text-muted-foreground">
                    {s.locations.length} commune(s) · {s.progress_done}/{s.progress_total || "?"}{" "}
                    prospects · créée le{" "}
                    {new Date(s.created_at).toLocaleDateString("fr-FR")}
                  </div>
                </div>
                <span
                  className={`inline-flex shrink-0 items-center rounded-full px-2.5 py-0.5 text-xs font-semibold ${STATUS_COLOR[s.status]}`}
                >
                  {STATUS_LABELS[s.status]}
                </span>
              </div>
            </Link>
          ))
        )}
      </div>
    </div>
  );
}
