"use client";

import { Trash2 } from "lucide-react";
import { useRouter } from "next/navigation";
import * as React from "react";
import { toast } from "sonner";

import { Button } from "@/components/ui/button";

import { deleteProspectAction } from "./actions";

export function DeleteProspectButton({
  prospectId,
  searchId,
}: {
  prospectId: string;
  searchId: string;
}): JSX.Element {
  const router = useRouter();
  const [pending, setPending] = React.useState(false);

  const onClick = async (): Promise<void> => {
    if (
      !confirm(
        "Supprimer ce prospect ?\n\n" +
          "Cette action :\n" +
          "• retire le prospect de NoxiasProspect ;\n" +
          "• supprime l'organisation, la personne et le deal Pipedrive associés (si exportés) ;\n" +
          "• ajoute le SIREN et le téléphone à la blacklist (RGPD opt-out)\n\n" +
          "Action irréversible.",
      )
    ) {
      return;
    }
    setPending(true);
    const res = await deleteProspectAction(prospectId);
    setPending(false);
    if (res.error) {
      toast.error(res.error);
      return;
    }
    toast.success("Prospect supprimé et opt-out enregistré.");
    router.push(`/searches/${searchId}`);
    router.refresh();
  };

  return (
    <Button variant="destructive" size="sm" onClick={onClick} disabled={pending}>
      <Trash2 className="mr-1.5 h-4 w-4" />
      {pending ? "Suppression…" : "Supprimer (RGPD)"}
    </Button>
  );
}
