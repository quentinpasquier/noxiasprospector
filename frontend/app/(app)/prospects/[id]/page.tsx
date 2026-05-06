import { ExternalLink, Mail, Phone } from "lucide-react";
import Link from "next/link";
import { notFound } from "next/navigation";

import { ScoreBadge } from "@/components/ui/score-badge";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { ApiError, api, type Prospect } from "@/lib/api";

import { DeleteProspectButton } from "./delete-button";

function fmtCurrency(eur: number | null): string {
  if (eur === null) return "—";
  return new Intl.NumberFormat("fr-FR", {
    style: "currency",
    currency: "EUR",
    maximumFractionDigits: 0,
  }).format(eur);
}

function ExternalRow({
  label,
  href,
  value,
}: {
  label: string;
  href: string | null;
  value: string | null;
}): JSX.Element {
  if (!href || !value)
    return (
      <div className="flex items-center justify-between text-sm">
        <span className="text-muted-foreground">{label}</span>
        <span>—</span>
      </div>
    );
  return (
    <div className="flex items-center justify-between text-sm">
      <span className="text-muted-foreground">{label}</span>
      <a
        href={href}
        target="_blank"
        rel="noreferrer"
        className="inline-flex items-center gap-1 font-medium text-primary hover:underline"
      >
        {value} <ExternalLink className="h-3 w-3" />
      </a>
    </div>
  );
}

export default async function ProspectDetailPage({
  params,
}: {
  params: Promise<{ id: string }>;
}): Promise<JSX.Element> {
  const { id } = await params;
  let p: Prospect;
  try {
    p = await api.getProspect(id);
  } catch (e) {
    if (e instanceof ApiError && e.status === 404) notFound();
    throw e;
  }

  const pappersUrl = p.siren ? `https://www.pappers.fr/entreprise/${p.siren}` : null;

  return (
    <div className="container max-w-5xl py-10">
      <Link
        href={`/searches/${p.search_id}`}
        className="text-sm text-muted-foreground hover:underline"
      >
        ← Retour à la recherche
      </Link>

      <div className="mt-4 flex items-start justify-between gap-4">
        <div className="min-w-0">
          <h1 className="truncate text-3xl font-bold tracking-tight">{p.name}</h1>
          {p.legal_name && p.legal_name !== p.name && (
            <p className="mt-1 text-sm text-muted-foreground">{p.legal_name}</p>
          )}
        </div>
        <div className="flex items-start gap-2">
          <ScoreBadge score={p.score} label={p.label} className="text-sm" />
          <DeleteProspectButton prospectId={p.id} searchId={p.search_id} />
        </div>
      </div>

      <div className="mt-8 grid gap-6 lg:grid-cols-2">
        <Card>
          <CardHeader>
            <CardTitle>Coordonnées</CardTitle>
          </CardHeader>
          <CardContent className="space-y-3">
            <div className="flex items-start justify-between gap-3 text-sm">
              <span className="text-muted-foreground">Adresse</span>
              <span className="text-right font-medium">
                {p.address ?? "—"}
                {p.postal_code && p.city && (
                  <>
                    <br />
                    {p.postal_code} {p.city}
                  </>
                )}
              </span>
            </div>
            <div className="flex items-center justify-between text-sm">
              <span className="text-muted-foreground">
                <Phone className="mr-1 inline h-3 w-3" />
                Téléphone
              </span>
              <span className="font-medium">{p.phone_e164 ?? "—"}</span>
            </div>
            <ExternalRow label="Site web" href={p.website} value={p.website} />
            <ExternalRow
              label="Google Maps"
              href={p.gmaps_url}
              value={p.gmaps_url ? "Voir la fiche" : null}
            />
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle>Légal & financier</CardTitle>
          </CardHeader>
          <CardContent className="space-y-3 text-sm">
            <div className="flex justify-between">
              <span className="text-muted-foreground">SIREN</span>
              <span className="font-medium tabular-nums">{p.siren ?? "—"}</span>
            </div>
            <div className="flex justify-between">
              <span className="text-muted-foreground">NAF</span>
              <span className="font-medium">{p.naf_code ?? "—"}</span>
            </div>
            <div className="flex justify-between">
              <span className="text-muted-foreground">Forme juridique</span>
              <span className="font-medium">{p.legal_form ?? "—"}</span>
            </div>
            <div className="flex justify-between">
              <span className="text-muted-foreground">Dirigeant</span>
              <span className="font-medium">{p.director_name ?? "—"}</span>
            </div>
            <div className="flex justify-between">
              <span className="text-muted-foreground">Effectif</span>
              <span className="font-medium">{p.employees_range ?? "—"}</span>
            </div>
            <div className="flex justify-between">
              <span className="text-muted-foreground">CA {p.financials_year ?? ""}</span>
              <span className="font-medium tabular-nums">{fmtCurrency(p.revenue_eur)}</span>
            </div>
            <div className="flex justify-between">
              <span className="text-muted-foreground">Résultat</span>
              <span className="font-medium tabular-nums">{fmtCurrency(p.profit_eur)}</span>
            </div>
            <ExternalRow
              label="Pappers"
              href={pappersUrl}
              value={pappersUrl ? "Ouvrir la fiche" : null}
            />
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle>Signaux Google Maps</CardTitle>
          </CardHeader>
          <CardContent className="space-y-3 text-sm">
            <div className="flex justify-between">
              <span className="text-muted-foreground">Catégorie</span>
              <span className="font-medium">{p.category ?? "—"}</span>
            </div>
            <div className="flex justify-between">
              <span className="text-muted-foreground">Note</span>
              <span className="font-medium tabular-nums">
                {p.rating?.toFixed(1) ?? "—"} / 5
              </span>
            </div>
            <div className="flex justify-between">
              <span className="text-muted-foreground">Avis</span>
              <span className="font-medium tabular-nums">{p.reviews_count ?? "—"}</span>
            </div>
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle>Réseaux sociaux</CardTitle>
          </CardHeader>
          <CardContent className="space-y-3">
            <ExternalRow label="Facebook" href={p.facebook_url} value={p.facebook_url} />
            <ExternalRow label="Instagram" href={p.instagram_url} value={p.instagram_url} />
            <ExternalRow label="LinkedIn" href={p.linkedin_url} value={p.linkedin_url} />
          </CardContent>
        </Card>
      </div>

      <p className="mt-8 text-xs text-muted-foreground">
        Phase 5 — l&apos;export Pipedrive de cette fiche arrive bientôt.{" "}
        <Mail className="inline h-3 w-3" />
      </p>
    </div>
  );
}
