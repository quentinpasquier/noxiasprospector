"use server";

import { revalidatePath } from "next/cache";
import { z } from "zod";

import { ApiError, api } from "@/lib/api";

const SIREN_RE = /^\d{9}$/;
const E164_RE = /^\+\d{8,15}$/;

const BlacklistSchema = z
  .object({
    siren: z
      .string()
      .trim()
      .regex(SIREN_RE, "SIREN doit faire 9 chiffres.")
      .optional()
      .or(z.literal("")),
    phone_e164: z
      .string()
      .trim()
      .regex(E164_RE, "Téléphone doit être au format E.164 (+33...).")
      .optional()
      .or(z.literal("")),
    reason: z.enum(["opt_out", "invalid", "competitor"]),
    note: z.string().max(2000).optional().or(z.literal("")),
  })
  .refine((d) => Boolean(d.siren) || Boolean(d.phone_e164), {
    message: "Renseigne un SIREN ou un téléphone.",
    path: ["siren"],
  });

export type AddBlacklistState = {
  errors?: Partial<Record<"siren" | "phone_e164" | "reason" | "_form", string>>;
};

export async function addBlacklistEntry(
  _prev: AddBlacklistState,
  formData: FormData,
): Promise<AddBlacklistState> {
  const raw = {
    siren: String(formData.get("siren") ?? "").trim() || undefined,
    phone_e164: String(formData.get("phone_e164") ?? "").trim() || undefined,
    reason: String(formData.get("reason") ?? "opt_out") as
      | "opt_out"
      | "invalid"
      | "competitor",
    note: String(formData.get("note") ?? "").trim() || undefined,
  };
  const parsed = BlacklistSchema.safeParse(raw);
  if (!parsed.success) {
    const errors: AddBlacklistState["errors"] = {};
    for (const issue of parsed.error.issues) {
      const key = issue.path[0];
      if (key === "siren" || key === "phone_e164" || key === "reason") {
        errors[key] = issue.message;
      }
    }
    return { errors };
  }

  try {
    await api.addBlacklist({
      siren: parsed.data.siren || null,
      phone_e164: parsed.data.phone_e164 || null,
      reason: parsed.data.reason,
      note: parsed.data.note ?? null,
    });
    revalidatePath("/blacklist");
    return {};
  } catch (e) {
    return {
      errors: {
        _form: e instanceof ApiError ? e.message : "Échec inattendu.",
      },
    };
  }
}

export async function removeBlacklistEntry(id: string): Promise<{ error?: string }> {
  try {
    await api.removeBlacklist(id);
    revalidatePath("/blacklist");
    return {};
  } catch (e) {
    return { error: e instanceof ApiError ? e.message : "Échec inattendu." };
  }
}
