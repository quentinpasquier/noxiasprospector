"use client";

import * as React from "react";
import { useFormState, useFormStatus } from "react-dom";
import { toast } from "sonner";

import { CommunesMultiSelect, type Commune } from "@/components/communes-multiselect";
import { RegionMap } from "@/components/region-map";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Label } from "@/components/ui/label";
import { Slider } from "@/components/ui/slider";
import { Textarea } from "@/components/ui/textarea";

import { createSearchAction, type SearchFormState } from "@/app/(app)/searches/actions";

const PRESETS = [
  { value: "default", label: "Standard (équilibré)" },
  { value: "btp", label: "BTP / artisans" },
  { value: "services", label: "Services aux entreprises" },
];

function SubmitButton(): JSX.Element {
  const { pending } = useFormStatus();
  return (
    <Button type="submit" size="lg" disabled={pending}>
      {pending ? "Lancement…" : "Lancer le ciblage"}
    </Button>
  );
}

const initialState: SearchFormState = {};

/**
 * Two-column targeting page: form on the left, OpenStreetMap on the right.
 * The map listens to the selected communes (via departments) and shows a
 * proportional marker per département.
 */
export function CiblerForm(): JSX.Element {
  const [communes, setCommunes] = React.useState<Commune[]>([]);
  const [limit, setLimit] = React.useState(100);
  const [preset, setPreset] = React.useState("default");
  const [state, formAction] = useFormState(createSearchAction, initialState);

  const departments = React.useMemo(
    () => communes.map((c) => c.department),
    [communes],
  );

  React.useEffect(() => {
    if (state.errors?._form) toast.error(state.errors._form);
  }, [state.errors?._form]);

  return (
    <div className="grid gap-6 lg:grid-cols-[minmax(0,1fr)_minmax(0,1fr)]">
      {/* ---------- Left: form ---------- */}
      <form action={formAction} className="space-y-4">
        <input type="hidden" name="locations" value={JSON.stringify(communes)} />
        <input type="hidden" name="limit" value={limit} />
        <input type="hidden" name="preset" value={preset} />

        <Card>
          <CardHeader>
            <CardTitle>Ciblage</CardTitle>
          </CardHeader>
          <CardContent className="space-y-5">
            <div className="space-y-2">
              <Label htmlFor="query">Mot-clé métier</Label>
              <Textarea
                id="query"
                name="query"
                rows={2}
                placeholder="Ex. : courtier en travaux, agence immobilière, plombier chauffagiste…"
                required
              />
              {state.errors?.query && (
                <p className="text-xs text-destructive">{state.errors.query}</p>
              )}
            </div>

            <div className="space-y-2">
              <Label>Communes (Auvergne-Rhône-Alpes)</Label>
              <CommunesMultiSelect value={communes} onChange={setCommunes} />
              {state.errors?.locations && (
                <p className="text-xs text-destructive">{state.errors.locations}</p>
              )}
            </div>

            <div className="space-y-3">
              <div className="flex items-center justify-between">
                <Label>Volume cible</Label>
                <span className="text-sm font-medium tabular-nums text-muted-foreground">
                  {limit} prospects max
                </span>
              </div>
              <Slider
                min={50}
                max={500}
                step={50}
                value={[limit]}
                onValueChange={(v) => setLimit(v[0] ?? 100)}
              />
            </div>

            <div className="space-y-2">
              <Label>Preset de scoring</Label>
              <div className="grid gap-2 sm:grid-cols-3">
                {PRESETS.map((p) => (
                  <button
                    type="button"
                    key={p.value}
                    onClick={() => setPreset(p.value)}
                    className={`rounded-md border px-3 py-2 text-left text-sm transition-colors ${
                      preset === p.value
                        ? "border-primary bg-primary/5 text-primary"
                        : "border-input hover:bg-accent"
                    }`}
                  >
                    {p.label}
                  </button>
                ))}
              </div>
            </div>
          </CardContent>
        </Card>

        <div className="flex justify-end">
          <SubmitButton />
        </div>
      </form>

      {/* ---------- Right: live map ---------- */}
      <div className="sticky top-6 h-[640px] lg:h-[720px]">
        <RegionMap selectedDepartments={departments} />
        <p className="mt-2 text-center text-xs text-muted-foreground">
          {communes.length === 0
            ? "Sélectionne des communes pour voir leur répartition."
            : `${communes.length} commune(s) sur ${new Set(departments).size} département(s).`}
        </p>
      </div>
    </div>
  );
}
