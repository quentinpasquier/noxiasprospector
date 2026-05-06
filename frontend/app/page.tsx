export default function HomePage(): JSX.Element {
  return (
    <main className="container flex min-h-screen flex-col items-center justify-center gap-6 py-16">
      <div className="text-center">
        <h1 className="text-4xl font-bold tracking-tight">NoxiasProspect</h1>
        <p className="mt-3 text-muted-foreground">
          Outil interne de prospection commerciale B2B.
        </p>
      </div>
      <div className="rounded-lg border bg-card p-6 text-card-foreground shadow-sm">
        <p className="text-sm text-muted-foreground">
          Phase 1 — scaffold opérationnel. Auth + recherches arrivent en Phase 2.
        </p>
      </div>
    </main>
  );
}
