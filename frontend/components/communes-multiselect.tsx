"use client";

import { Check, ChevronsUpDown, X } from "lucide-react";
import { Command } from "cmdk";
import * as React from "react";

import { Badge } from "@/components/ui/badge";
import { Popover, PopoverContent, PopoverTrigger } from "@/components/ui/popover";
import { cn } from "@/lib/utils";

import communesData from "@/lib/communes-ara.json";

export type Commune = {
  name: string;
  postal_code: string;
  department: string;
};

const ALL_COMMUNES: Commune[] = communesData.communes;

const DEPT_LABELS: Record<string, string> = {
  "01": "Ain",
  "03": "Allier",
  "07": "Ardèche",
  "15": "Cantal",
  "26": "Drôme",
  "38": "Isère",
  "42": "Loire",
  "43": "Haute-Loire",
  "63": "Puy-de-Dôme",
  "69": "Rhône",
  "73": "Savoie",
  "74": "Haute-Savoie",
};

function communeKey(c: Commune): string {
  return `${c.postal_code}-${c.name}`;
}

export function CommunesMultiSelect({
  value,
  onChange,
  placeholder = "Sélectionner des villes…",
}: {
  value: Commune[];
  onChange: (next: Commune[]) => void;
  placeholder?: string;
}): JSX.Element {
  const [open, setOpen] = React.useState(false);
  const [search, setSearch] = React.useState("");

  const selectedKeys = React.useMemo(
    () => new Set(value.map(communeKey)),
    [value],
  );

  const filtered = React.useMemo(() => {
    const q = search.trim().toLowerCase();
    if (!q) return ALL_COMMUNES;
    return ALL_COMMUNES.filter((c) => {
      return (
        c.name.toLowerCase().includes(q) ||
        c.postal_code.startsWith(q) ||
        DEPT_LABELS[c.department]?.toLowerCase().includes(q)
      );
    });
  }, [search]);

  const toggle = (commune: Commune): void => {
    const key = communeKey(commune);
    if (selectedKeys.has(key)) {
      onChange(value.filter((c) => communeKey(c) !== key));
    } else {
      onChange([...value, commune]);
    }
  };

  const remove = (commune: Commune): void => {
    onChange(value.filter((c) => communeKey(c) !== communeKey(commune)));
  };

  return (
    <div className="space-y-2">
      <Popover open={open} onOpenChange={setOpen}>
        <PopoverTrigger asChild>
          <button
            type="button"
            aria-haspopup="listbox"
            aria-expanded={open}
            className={cn(
              "flex h-10 w-full items-center justify-between rounded-md border border-input",
              "bg-background px-3 py-2 text-sm ring-offset-background",
              "focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring",
              "focus-visible:ring-offset-2",
            )}
          >
            <span className={value.length === 0 ? "text-muted-foreground" : ""}>
              {value.length === 0 ? placeholder : `${value.length} ville(s) sélectionnée(s)`}
            </span>
            <ChevronsUpDown className="ml-2 h-4 w-4 opacity-50" />
          </button>
        </PopoverTrigger>
        <PopoverContent className="w-[400px] p-0" align="start">
          <Command className="overflow-hidden rounded-md">
            <div className="flex items-center border-b px-3">
              <Command.Input
                placeholder="Chercher une ville, code postal, département…"
                value={search}
                onValueChange={setSearch}
                className="flex h-10 w-full bg-transparent py-2 text-sm outline-none placeholder:text-muted-foreground"
              />
            </div>
            <Command.List className="max-h-72 overflow-y-auto">
              <Command.Empty className="py-6 text-center text-sm text-muted-foreground">
                Aucune commune trouvée.
              </Command.Empty>
              {filtered.slice(0, 200).map((commune) => {
                const key = communeKey(commune);
                const checked = selectedKeys.has(key);
                return (
                  <Command.Item
                    key={key}
                    value={`${commune.name} ${commune.postal_code}`}
                    onSelect={() => toggle(commune)}
                    className={cn(
                      "flex cursor-pointer items-center gap-2 px-3 py-2 text-sm",
                      "aria-selected:bg-accent aria-selected:text-accent-foreground",
                    )}
                  >
                    <Check
                      className={cn("h-4 w-4", checked ? "opacity-100" : "opacity-0")}
                    />
                    <span className="flex-1">{commune.name}</span>
                    <span className="text-xs text-muted-foreground tabular-nums">
                      {commune.postal_code}
                    </span>
                    <span className="text-xs text-muted-foreground">
                      ({DEPT_LABELS[commune.department]})
                    </span>
                  </Command.Item>
                );
              })}
            </Command.List>
          </Command>
        </PopoverContent>
      </Popover>

      {value.length > 0 && (
        <div className="flex flex-wrap gap-1.5">
          {value.map((c) => (
            <Badge key={communeKey(c)} variant="secondary" className="gap-1">
              {c.name} <span className="text-muted-foreground">{c.postal_code}</span>
              <button
                type="button"
                onClick={() => remove(c)}
                className="ml-1 rounded-full hover:bg-background"
                aria-label={`Retirer ${c.name}`}
              >
                <X className="h-3 w-3" />
              </button>
            </Badge>
          ))}
        </div>
      )}
    </div>
  );
}
