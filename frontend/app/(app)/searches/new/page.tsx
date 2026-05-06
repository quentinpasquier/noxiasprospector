import { SearchForm } from "./search-form";

export default function NewSearchPage(): JSX.Element {
  return (
    <div className="container max-w-3xl py-10">
      <h1 className="text-3xl font-bold tracking-tight">Nouvelle recherche</h1>
      <p className="mt-1 text-sm text-muted-foreground">
        Lance une prospection en sélectionnant un mot-clé métier et un périmètre
        géographique en Auvergne-Rhône-Alpes.
      </p>
      <div className="mt-8">
        <SearchForm />
      </div>
    </div>
  );
}
