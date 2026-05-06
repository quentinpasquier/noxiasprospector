import { cn } from "@/lib/utils";

const LABEL_STYLES: Record<string, string> = {
  Hot: "bg-score-hot/15 text-score-hot border-score-hot/30",
  Warm: "bg-score-warm/15 text-score-warm border-score-warm/30",
  Cold: "bg-score-cold/15 text-score-cold border-score-cold/30",
  "À qualifier": "bg-score-unknown/15 text-score-unknown border-score-unknown/30",
};

export function ScoreBadge({
  score,
  label,
  className,
}: {
  score: number | null;
  label: string | null;
  className?: string;
}): JSX.Element {
  const style = label ? LABEL_STYLES[label] : LABEL_STYLES["À qualifier"];
  return (
    <span
      className={cn(
        "inline-flex items-center gap-1.5 rounded-full border px-2.5 py-0.5 text-xs font-semibold",
        style,
        className,
      )}
    >
      <span className="font-bold tabular-nums">{score ?? "—"}</span>
      <span className="opacity-80">{label ?? "À qualifier"}</span>
    </span>
  );
}
