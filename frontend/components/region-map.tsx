"use client";

import dynamic from "next/dynamic";

import { Skeleton } from "@/components/ui/skeleton";

/**
 * Wrapper around `RegionMapInner` that disables SSR — Leaflet needs the
 * `window` object, which is not available during Next.js prerendering.
 */
const RegionMapInner = dynamic(
  () => import("./region-map-inner").then((m) => m.RegionMapInner),
  {
    ssr: false,
    loading: () => <Skeleton className="h-full w-full rounded-lg" />,
  },
);

export function RegionMap({
  selectedDepartments,
}: {
  selectedDepartments: string[];
}): JSX.Element {
  return (
    <div className="h-full w-full overflow-hidden rounded-lg border bg-card">
      <RegionMapInner selectedDepartments={selectedDepartments} />
    </div>
  );
}
