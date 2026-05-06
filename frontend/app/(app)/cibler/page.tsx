import { CiblerForm } from "./cibler-form";

export default function CiblerPage(): JSX.Element {
  return (
    <div className="container max-w-7xl py-10">
      <div className="mb-8">
        <h1 className="text-3xl font-bold tracking-tight">Cibler</h1>
        <p className="mt-1 text-sm text-muted-foreground">
          Construis une base prospects ciblée pour une intégration rapide dans
          Pipedrive : choisis ton mot-clé métier, ton périmètre Auvergne-Rhône-Alpes
          et ton volume.
        </p>
      </div>
      <CiblerForm />
    </div>
  );
}
