import { notFound } from "next/navigation";
import Link from "next/link";

import { Button } from "@/components/ui/button";
import { ApiError, api } from "@/lib/api";

import { LiveView } from "./live-view";

export default async function SearchDetailPage({
  params,
}: {
  params: Promise<{ id: string }>;
}): Promise<JSX.Element> {
  const { id } = await params;
  let search;
  let prospects;
  try {
    [search, prospects] = await Promise.all([api.getSearch(id), api.listProspects(id)]);
  } catch (e) {
    if (e instanceof ApiError && e.status === 404) notFound();
    throw e;
  }

  return (
    <div className="container max-w-6xl py-10">
      <div className="mb-6 flex items-center justify-between">
        <Link href="/searches" className="text-sm text-muted-foreground hover:underline">
          ← Toutes les recherches
        </Link>
        <Button asChild variant="outline" size="sm">
          <a href={`/api/proxy/searches/${id}/export.csv`}>Exporter CSV</a>
        </Button>
      </div>
      <LiveView initialSearch={search} initialProspects={prospects} />
    </div>
  );
}
