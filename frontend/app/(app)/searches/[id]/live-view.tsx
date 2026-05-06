"use client";

import { useVirtualizer } from "@tanstack/react-virtual";
import { ExternalLink } from "lucide-react";
import Link from "next/link";
import * as React from "react";

import { ScoreBadge } from "@/components/ui/score-badge";
import { Progress } from "@/components/ui/progress";
import { Skeleton } from "@/components/ui/skeleton";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import type { Prospect, Search, SearchStatus } from "@/lib/api";

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

type Props = {
  initialSearch: Search;
  initialProspects: Prospect[];
};

export function LiveView({ initialSearch, initialProspects }: Props): JSX.Element {
  const [search, setSearch] = React.useState<Search>(initialSearch);
  const [prospects, setProspects] = React.useState<Prospect[]>(initialProspects);
  const [streaming, setStreaming] = React.useState(initialSearch.status !== "completed" && initialSearch.status !== "failed");

  // SSE subscription while the job is alive.
  React.useEffect(() => {
    if (!streaming) return;
    const es = new EventSource(`/api/sse/searches/${search.id}`);
    es.addEventListener("progress", async (event) => {
      try {
        const data = JSON.parse((event as MessageEvent).data) as {
          status: SearchStatus;
          progress_done: number;
          progress_total: number;
          error_message: string | null;
        };
        setSearch((prev) => ({ ...prev, ...data }));
        // Refresh prospects list — the backend has been adding rows.
        const res = await fetch(`/api/proxy/searches/${search.id}/prospects`, {
          cache: "no-store",
        });
        if (res.ok) setProspects((await res.json()) as Prospect[]);
        if (data.status === "completed" || data.status === "failed") {
          setStreaming(false);
        }
      } catch {
        // ignore malformed event
      }
    });
    es.onerror = () => {
      es.close();
      setStreaming(false);
    };
    return () => es.close();
  }, [search.id, streaming]);

  const percent =
    search.progress_total > 0
      ? Math.round((search.progress_done / search.progress_total) * 100)
      : search.status === "completed"
        ? 100
        : 0;

  return (
    <div className="space-y-6">
      <div className="rounded-xl border bg-card p-6">
        <div className="flex items-center justify-between gap-4">
          <div className="min-w-0">
            <h1 className="truncate text-2xl font-bold tracking-tight">{search.query}</h1>
            <p className="mt-1 text-sm text-muted-foreground">
              {search.locations.length} commune(s) ciblée(s) · créée le{" "}
              {new Date(search.created_at).toLocaleString("fr-FR")}
            </p>
          </div>
          <span
            className={`inline-flex items-center rounded-full px-3 py-1 text-xs font-semibold ${STATUS_COLOR[search.status]}`}
          >
            {STATUS_LABELS[search.status]}
          </span>
        </div>
        <div className="mt-5 space-y-2">
          <div className="flex justify-between text-xs text-muted-foreground">
            <span>
              Progression : {search.progress_done} / {search.progress_total || "?"}
            </span>
            <span className="tabular-nums">{percent}%</span>
          </div>
          <Progress value={percent} />
        </div>
        {search.error_message && (
          <p className="mt-3 rounded-md bg-destructive/10 px-3 py-2 text-sm text-destructive">
            {search.error_message}
          </p>
        )}
      </div>

      <ProspectsTable prospects={prospects} streaming={streaming} />
    </div>
  );
}

function ProspectsTable({
  prospects,
  streaming,
}: {
  prospects: Prospect[];
  streaming: boolean;
}): JSX.Element {
  const parentRef = React.useRef<HTMLDivElement>(null);
  const rowVirtualizer = useVirtualizer({
    count: prospects.length,
    getScrollElement: () => parentRef.current,
    estimateSize: () => 56,
    overscan: 8,
  });

  return (
    <div className="rounded-xl border bg-card">
      <div className="flex items-center justify-between border-b px-6 py-3">
        <div className="text-sm font-medium">
          {prospects.length} prospect(s)
          {streaming && (
            <span className="ml-2 text-xs text-muted-foreground">· enrichissement en cours…</span>
          )}
        </div>
      </div>

      {prospects.length === 0 ? (
        <div className="space-y-2 p-6">
          {streaming ? (
            <>
              <Skeleton className="h-12 w-full" />
              <Skeleton className="h-12 w-full" />
              <Skeleton className="h-12 w-full" />
            </>
          ) : (
            <p className="py-8 text-center text-sm text-muted-foreground">
              Aucun prospect trouvé pour cette recherche.
            </p>
          )}
        </div>
      ) : (
        <div ref={parentRef} className="max-h-[600px] overflow-auto">
          <Table>
            <TableHeader className="sticky top-0 z-10 bg-card">
              <TableRow>
                <TableHead className="w-[40%]">Entreprise</TableHead>
                <TableHead>Ville</TableHead>
                <TableHead>Score</TableHead>
                <TableHead className="text-right">Note</TableHead>
                <TableHead className="text-right">Avis</TableHead>
                <TableHead className="text-right" />
              </TableRow>
            </TableHeader>
            <TableBody
              style={{
                height: `${rowVirtualizer.getTotalSize()}px`,
                position: "relative",
              }}
            >
              {rowVirtualizer.getVirtualItems().map((virtualRow) => {
                const p = prospects[virtualRow.index];
                if (!p) return null;
                return (
                  <TableRow
                    key={p.id}
                    style={{
                      position: "absolute",
                      top: 0,
                      left: 0,
                      right: 0,
                      transform: `translateY(${virtualRow.start}px)`,
                    }}
                  >
                    <TableCell>
                      <div className="font-medium">{p.name}</div>
                      <div className="text-xs text-muted-foreground">
                        {p.legal_name && p.legal_name !== p.name ? p.legal_name : p.category}
                      </div>
                    </TableCell>
                    <TableCell className="text-sm">
                      {p.city ?? "—"}{" "}
                      {p.postal_code && (
                        <span className="text-muted-foreground">{p.postal_code}</span>
                      )}
                    </TableCell>
                    <TableCell>
                      <ScoreBadge score={p.score} label={p.label} />
                    </TableCell>
                    <TableCell className="text-right tabular-nums">
                      {p.rating?.toFixed(1) ?? "—"}
                    </TableCell>
                    <TableCell className="text-right tabular-nums">
                      {p.reviews_count ?? "—"}
                    </TableCell>
                    <TableCell className="text-right">
                      <Link
                        href={`/prospects/${p.id}`}
                        className="inline-flex items-center text-xs font-medium text-primary hover:underline"
                      >
                        Voir <ExternalLink className="ml-1 h-3 w-3" />
                      </Link>
                    </TableCell>
                  </TableRow>
                );
              })}
            </TableBody>
          </Table>
        </div>
      )}
    </div>
  );
}
