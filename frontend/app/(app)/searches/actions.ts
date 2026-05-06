"use server";

import { revalidatePath } from "next/cache";
import { redirect } from "next/navigation";
import { z } from "zod";

import { api } from "@/lib/api";

const PRESETS = ["default", "btp", "services"] as const;

const SearchSchema = z.object({
  query: z.string().trim().min(2, "Le mot-clé doit faire au moins 2 caractères.").max(500),
  locations: z
    .array(
      z.object({
        city: z.string().min(1),
        postal_code: z.string().nullable(),
      }),
    )
    .min(1, "Sélectionne au moins une commune.")
    .max(50),
  limit: z.number().int().min(50).max(500),
  preset: z.enum(PRESETS),
});

export type SearchFormState = {
  errors?: Partial<Record<"query" | "locations" | "limit" | "preset" | "_form", string>>;
};

export async function createSearchAction(
  _prev: SearchFormState,
  formData: FormData,
): Promise<SearchFormState> {
  const raw = {
    query: String(formData.get("query") ?? ""),
    locations: JSON.parse(String(formData.get("locations") ?? "[]")) as unknown,
    limit: Number(formData.get("limit") ?? 100),
    preset: String(formData.get("preset") ?? "default"),
  };

  const parsed = SearchSchema.safeParse(raw);
  if (!parsed.success) {
    const errors: SearchFormState["errors"] = {};
    for (const issue of parsed.error.issues) {
      const key = issue.path[0];
      if (key === "query" || key === "locations" || key === "limit" || key === "preset") {
        errors[key] = issue.message;
      }
    }
    return { errors };
  }

  let search;
  try {
    search = await api.createSearch(parsed.data);
  } catch (e) {
    return {
      errors: {
        _form: e instanceof Error ? e.message : "Échec de la création de la recherche.",
      },
    };
  }

  revalidatePath("/searches");
  redirect(`/searches/${search.id}`);
}
