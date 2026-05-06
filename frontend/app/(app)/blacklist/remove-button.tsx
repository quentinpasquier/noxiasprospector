"use client";

import { Trash2 } from "lucide-react";
import * as React from "react";
import { useRouter } from "next/navigation";
import { toast } from "sonner";

import { Button } from "@/components/ui/button";

import { removeBlacklistEntry } from "./actions";

export function RemoveButton({ id }: { id: string }): JSX.Element {
  const router = useRouter();
  const [pending, setPending] = React.useState(false);

  const onClick = async (): Promise<void> => {
    if (!confirm("Retirer cette entrée de la blacklist ?")) return;
    setPending(true);
    const res = await removeBlacklistEntry(id);
    setPending(false);
    if (res.error) {
      toast.error(res.error);
      return;
    }
    toast.success("Entrée supprimée.");
    router.refresh();
  };

  return (
    <Button
      variant="ghost"
      size="icon"
      aria-label="Supprimer"
      onClick={onClick}
      disabled={pending}
    >
      <Trash2 className="h-4 w-4" />
    </Button>
  );
}
