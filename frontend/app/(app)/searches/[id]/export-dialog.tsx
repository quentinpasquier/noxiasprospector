"use client";

import * as React from "react";
import { toast } from "sonner";

import { Button } from "@/components/ui/button";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
} from "@/components/ui/dialog";
import { Skeleton } from "@/components/ui/skeleton";
import type { DuplicateReason, ExportPreviewItem } from "@/lib/api";

import { fetchExportPreview, runExport } from "./export-actions";

const REASON_LABEL: Record<DuplicateReason, string> = {
  none: "Nouveau",
  phone: "Doublon (téléphone)",
  siren: "Doublon (SIREN)",
  already_exported: "Déjà exporté",
};

const REASON_STYLE: Record<DuplicateReason, string> = {
  none: "bg-score-warm/15 text-score-warm",
  phone: "bg-score-hot/15 text-score-hot",
  siren: "bg-score-hot/15 text-score-hot",
  already_exported: "bg-muted text-muted-foreground",
};

export function ExportDialog({ searchId }: { searchId: string }): JSX.Element {
  const [open, setOpen] = React.useState(false);
  const [items, setItems] = React.useState<ExportPreviewItem[] | null>(null);
  const [error, setError] = React.useState<string | null>(null);
  const [loading, setLoading] = React.useState(false);
  const [skipIds, setSkipIds] = React.useState<Set<string>>(new Set());
  const [submitting, setSubmitting] = React.useState(false);

  // Load preview when the dialog opens.
  React.useEffect(() => {
    if (!open) return;
    setLoading(true);
    setError(null);
    void fetchExportPreview(searchId).then((res) => {
      setLoading(false);
      if (res.error) {
        setError(res.error);
        return;
      }
      setItems(res.data?.items ?? []);
      // Auto-skip duplicates and already-exported by default.
      setSkipIds(
        new Set(
          (res.data?.items ?? [])
            .filter((it) => it.duplicate_reason !== "none")
            .map((it) => it.prospect_id),
        ),
      );
    });
  }, [open, searchId]);

  const toggle = (id: string): void => {
    setSkipIds((prev) => {
      const next = new Set(prev);
      if (next.has(id)) next.delete(id);
      else next.add(id);
      return next;
    });
  };

  const newCount = items?.filter((it) => it.duplicate_reason === "none").length ?? 0;
  const dupeCount = (items?.length ?? 0) - newCount;
  const willExport = (items?.length ?? 0) - skipIds.size;

  const onConfirm = async (): Promise<void> => {
    if (!items) return;
    setSubmitting(true);
    const res = await runExport(searchId, Array.from(skipIds));
    setSubmitting(false);
    if (res.error) {
      toast.error(res.error);
      return;
    }
    if (res.data) {
      toast.success(
        `Pipedrive : ${res.data.created} créé(s), ${res.data.skipped} ignoré(s), ${res.data.failed} échec(s).`,
      );
      setOpen(false);
    }
  };

  return (
    <Dialog open={open} onOpenChange={setOpen}>
      <DialogTrigger asChild>
        <Button variant="default" size="sm">
          Exporter vers Pipedrive
        </Button>
      </DialogTrigger>
      <DialogContent className="max-w-3xl">
        <DialogHeader>
          <DialogTitle>Export vers Pipedrive</DialogTitle>
          <DialogDescription>
            Pipedrive est consulté pour identifier les doublons par téléphone (E.164) puis
            par SIREN. Les fiches déjà exportées depuis NoxiasProspect sont également
            écartées.
          </DialogDescription>
        </DialogHeader>

        {error && (
          <div className="rounded-md bg-destructive/10 px-3 py-2 text-sm text-destructive">
            {error}
          </div>
        )}

        {loading && (
          <div className="space-y-2 py-4">
            <Skeleton className="h-10 w-full" />
            <Skeleton className="h-10 w-full" />
            <Skeleton className="h-10 w-full" />
          </div>
        )}

        {items && !loading && (
          <>
            <div className="flex flex-wrap gap-2 text-xs text-muted-foreground">
              <span>{items.length} prospects analysés</span>
              <span>·</span>
              <span>{newCount} nouveau(x)</span>
              <span>·</span>
              <span>{dupeCount} doublon(s)</span>
              <span>·</span>
              <span className="font-medium text-foreground">
                {willExport} à importer
              </span>
            </div>

            <div className="max-h-80 overflow-auto rounded-md border">
              <table className="w-full text-sm">
                <thead className="sticky top-0 bg-muted/50 text-xs uppercase tracking-wide">
                  <tr>
                    <th className="px-3 py-2 text-left">Prospect</th>
                    <th className="px-3 py-2 text-left">Statut</th>
                    <th className="px-3 py-2 text-right">Importer</th>
                  </tr>
                </thead>
                <tbody>
                  {items.map((it) => {
                    const skipped = skipIds.has(it.prospect_id);
                    const disabled = it.duplicate_reason === "already_exported";
                    return (
                      <tr key={it.prospect_id} className="border-t">
                        <td className="px-3 py-2">
                          <div className="font-medium">{it.name}</div>
                          <div className="text-xs text-muted-foreground">
                            {it.siren ? `SIREN ${it.siren}` : ""}
                            {it.siren && it.phone_e164 ? " · " : ""}
                            {it.phone_e164 ?? ""}
                          </div>
                        </td>
                        <td className="px-3 py-2">
                          <span
                            className={`inline-flex items-center rounded-full px-2 py-0.5 text-xs font-medium ${REASON_STYLE[it.duplicate_reason]}`}
                          >
                            {REASON_LABEL[it.duplicate_reason]}
                          </span>
                        </td>
                        <td className="px-3 py-2 text-right">
                          <input
                            type="checkbox"
                            disabled={disabled}
                            checked={!skipped && !disabled}
                            onChange={() => toggle(it.prospect_id)}
                            className="h-4 w-4 cursor-pointer"
                          />
                        </td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </div>
          </>
        )}

        <DialogFooter>
          <Button variant="ghost" onClick={() => setOpen(false)} disabled={submitting}>
            Annuler
          </Button>
          <Button
            onClick={onConfirm}
            disabled={loading || submitting || !items || willExport === 0}
          >
            {submitting ? "Export en cours…" : `Importer ${willExport} prospect(s)`}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
