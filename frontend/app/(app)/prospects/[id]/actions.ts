"use server";

import { revalidatePath } from "next/cache";

import { ApiError, api } from "@/lib/api";

export async function deleteProspectAction(
  id: string,
): Promise<{ error?: string }> {
  try {
    await api.deleteProspect(id);
    revalidatePath("/searches", "layout");
    return {};
  } catch (e) {
    return {
      error: e instanceof ApiError ? e.message : "Échec de la suppression.",
    };
  }
}
