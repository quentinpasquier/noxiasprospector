"use client";

import * as React from "react";
import { useFormState, useFormStatus } from "react-dom";
import { toast } from "sonner";

import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";

import { addBlacklistEntry, type AddBlacklistState } from "./actions";

const REASONS = [
  { value: "opt_out", label: "Opt-out (RGPD art. 21)" },
  { value: "invalid", label: "Donnée invalide" },
  { value: "competitor", label: "Concurrent" },
];

function SubmitButton(): JSX.Element {
  const { pending } = useFormStatus();
  return (
    <Button type="submit" disabled={pending}>
      {pending ? "Ajout…" : "Ajouter à la blacklist"}
    </Button>
  );
}

const initial: AddBlacklistState = {};

export function BlacklistForm(): JSX.Element {
  const [state, action] = useFormState(addBlacklistEntry, initial);

  React.useEffect(() => {
    if (state.errors?._form) {
      toast.error(state.errors._form);
    } else if (Object.keys(state.errors ?? {}).length === 0 && state !== initial) {
      // success state has no errors and is not the initial sentinel
      toast.success("Entrée ajoutée à la blacklist.");
    }
  }, [state]);

  return (
    <form action={action} className="space-y-4 rounded-lg border bg-card p-6">
      <h2 className="text-base font-semibold">Ajouter une opt-out</h2>
      <p className="text-xs text-muted-foreground">
        Renseigne un SIREN (9 chiffres) ou un téléphone E.164 (`+33…`). Toute
        future recherche écartera ces identifiants automatiquement.
      </p>

      <div className="grid gap-4 sm:grid-cols-2">
        <div className="space-y-1">
          <Label htmlFor="siren">SIREN</Label>
          <Input id="siren" name="siren" placeholder="123456789" />
          {state.errors?.siren && (
            <p className="text-xs text-destructive">{state.errors.siren}</p>
          )}
        </div>
        <div className="space-y-1">
          <Label htmlFor="phone_e164">Téléphone (E.164)</Label>
          <Input id="phone_e164" name="phone_e164" placeholder="+33472001122" />
          {state.errors?.phone_e164 && (
            <p className="text-xs text-destructive">{state.errors.phone_e164}</p>
          )}
        </div>
      </div>

      <div className="space-y-1">
        <Label htmlFor="reason">Motif</Label>
        <select
          id="reason"
          name="reason"
          defaultValue="opt_out"
          className="flex h-10 w-full rounded-md border border-input bg-background px-3 py-2 text-sm"
        >
          {REASONS.map((r) => (
            <option key={r.value} value={r.value}>
              {r.label}
            </option>
          ))}
        </select>
      </div>

      <div className="space-y-1">
        <Label htmlFor="note">Note (optionnel)</Label>
        <Textarea
          id="note"
          name="note"
          rows={2}
          placeholder="Référence ticket, demande email…"
        />
      </div>

      <div className="flex justify-end">
        <SubmitButton />
      </div>
    </form>
  );
}
