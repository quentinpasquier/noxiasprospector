"use server";

import { revalidatePath } from "next/cache";

import { ApiError, api, type ExportPreview, type ExportResponse } from "@/lib/api";

export type PreviewState = {
  data?: ExportPreview;
  error?: string;
};

export type RunState = {
  data?: ExportResponse;
  error?: string;
};

export async function fetchExportPreview(searchId: string): Promise<PreviewState> {
  try {
    const data = await api.previewExport(searchId);
    return { data };
  } catch (e) {
    if (e instanceof ApiError) return { error: e.message };
    return { error: "Erreur inattendue lors de la prévisualisation." };
  }
}

export async function runExport(
  searchId: string,
  skipIds: string[],
): Promise<RunState> {
  try {
    const data = await api.runExport(searchId, skipIds);
    revalidatePath(`/searches/${searchId}`);
    return { data };
  } catch (e) {
    if (e instanceof ApiError) return { error: e.message };
    return { error: "Erreur inattendue lors de l'export." };
  }
}
