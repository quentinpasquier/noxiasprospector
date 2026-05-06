import { api, type BlacklistReason } from "@/lib/api";

import { BlacklistForm } from "./blacklist-form";
import { RemoveButton } from "./remove-button";

const REASON_LABEL: Record<BlacklistReason, string> = {
  opt_out: "Opt-out",
  invalid: "Invalide",
  competitor: "Concurrent",
};

export default async function BlacklistPage(): Promise<JSX.Element> {
  const entries = await api.listBlacklist();

  return (
    <div className="container max-w-4xl py-10">
      <h1 className="text-3xl font-bold tracking-tight">Blacklist (opt-out)</h1>
      <p className="mt-1 text-sm text-muted-foreground">
        Toute recherche future ignorera les SIREN et téléphones listés ici.
        Conformité RGPD : article 21 (droit d&apos;opposition).
      </p>

      <div className="mt-8 grid gap-6 lg:grid-cols-[1fr_minmax(0,1.4fr)]">
        <BlacklistForm />

        <div className="rounded-lg border bg-card">
          <div className="border-b px-4 py-3 text-sm font-medium">
            {entries.length} entrée(s)
          </div>
          {entries.length === 0 ? (
            <p className="px-4 py-8 text-center text-sm text-muted-foreground">
              Aucune entrée pour le moment.
            </p>
          ) : (
            <table className="w-full text-sm">
              <thead className="bg-muted/30 text-xs uppercase tracking-wide">
                <tr>
                  <th className="px-4 py-2 text-left">Identifiant</th>
                  <th className="px-4 py-2 text-left">Motif</th>
                  <th className="px-4 py-2 text-left">Note</th>
                  <th className="px-4 py-2 text-right">Ajouté le</th>
                  <th className="px-4 py-2" />
                </tr>
              </thead>
              <tbody>
                {entries.map((e) => (
                  <tr key={e.id} className="border-t">
                    <td className="px-4 py-2 font-mono text-xs">
                      {e.siren ? `SIREN ${e.siren}` : null}
                      {e.siren && e.phone_e164 ? <br /> : null}
                      {e.phone_e164 ?? null}
                    </td>
                    <td className="px-4 py-2">{REASON_LABEL[e.reason]}</td>
                    <td className="max-w-xs truncate px-4 py-2 text-muted-foreground">
                      {e.note ?? "—"}
                    </td>
                    <td className="px-4 py-2 text-right text-xs text-muted-foreground tabular-nums">
                      {new Date(e.created_at).toLocaleDateString("fr-FR")}
                    </td>
                    <td className="px-4 py-2 text-right">
                      <RemoveButton id={e.id} />
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
        </div>
      </div>
    </div>
  );
}
