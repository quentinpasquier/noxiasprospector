/**
 * Typed fetch helpers that forward the user's Auth0 access token to the
 * FastAPI backend. Use these from server components / server actions only —
 * the access token must never reach the browser.
 */

import { auth } from "@/auth";

const API_BASE = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

export class ApiError extends Error {
  constructor(
    public readonly status: number,
    message: string,
  ) {
    super(message);
    this.name = "ApiError";
  }
}

async function authedFetch<T>(path: string, init: RequestInit = {}): Promise<T> {
  const session = await auth();
  if (!session?.accessToken) {
    throw new ApiError(401, "Not authenticated.");
  }

  const response = await fetch(`${API_BASE}/api/v1${path}`, {
    ...init,
    headers: {
      "Content-Type": "application/json",
      Authorization: `Bearer ${session.accessToken}`,
      ...init.headers,
    },
    cache: "no-store",
  });

  if (!response.ok) {
    const detail = await response.text();
    throw new ApiError(response.status, detail || response.statusText);
  }

  return (await response.json()) as T;
}

export type Me = {
  id: string;
  email: string;
  name: string | null;
  picture_url: string | null;
  role: "admin" | "sales";
  last_login_at: string | null;
  created_at: string;
};

export type SearchStatus = "pending" | "running" | "completed" | "failed";

export type LocationInput = {
  city: string;
  postal_code: string | null;
};

export type Search = {
  id: string;
  query: string;
  locations: { city?: string; postal_code?: string | null }[];
  status: SearchStatus;
  progress_total: number;
  progress_done: number;
  error_message: string | null;
  created_at: string;
  updated_at: string;
};

export type SearchCreatePayload = {
  query: string;
  locations: LocationInput[];
  limit: number;
  preset: string;
};

export type ProspectLabel = "Hot" | "Warm" | "Cold" | "À qualifier";

export type Prospect = {
  id: string;
  search_id: string;
  name: string;
  address: string | null;
  city: string | null;
  postal_code: string | null;
  phone_e164: string | null;
  website: string | null;
  gmaps_url: string | null;
  category: string | null;
  rating: number | null;
  reviews_count: number | null;
  siren: string | null;
  naf_code: string | null;
  legal_name: string | null;
  legal_form: string | null;
  creation_date: string | null;
  director_name: string | null;
  employees_range: string | null;
  revenue_eur: number | null;
  profit_eur: number | null;
  financials_year: number | null;
  facebook_url: string | null;
  instagram_url: string | null;
  linkedin_url: string | null;
  score: number | null;
  label: ProspectLabel | null;
  created_at: string;
};

export const api = {
  me: () => authedFetch<Me>("/auth/me"),

  listSearches: () => authedFetch<Search[]>("/searches"),

  createSearch: (payload: SearchCreatePayload) =>
    authedFetch<Search>("/searches", {
      method: "POST",
      body: JSON.stringify(payload),
    }),

  getSearch: (id: string) => authedFetch<Search>(`/searches/${id}`),

  listProspects: (searchId: string) =>
    authedFetch<Prospect[]>(`/searches/${searchId}/prospects`),

  getProspect: (id: string) => authedFetch<Prospect>(`/prospects/${id}`),

  previewExport: (searchId: string) =>
    authedFetch<ExportPreview>(`/searches/${searchId}/exports/pipedrive/preview`, {
      method: "POST",
    }),

  runExport: (searchId: string, skip_prospect_ids: string[]) =>
    authedFetch<ExportResponse>(`/searches/${searchId}/exports/pipedrive`, {
      method: "POST",
      body: JSON.stringify({ skip_prospect_ids }),
    }),
};

// ----- Export schemas -----
export type DuplicateReason = "none" | "phone" | "siren" | "already_exported";

export type ExportPreviewItem = {
  prospect_id: string;
  name: string;
  siren: string | null;
  phone_e164: string | null;
  duplicate_reason: DuplicateReason;
  duplicate_pipedrive_id: number | null;
};

export type ExportPreview = { items: ExportPreviewItem[] };

export type ExportResultItem = {
  prospect_id: string;
  status: "created" | "skipped" | "failed";
  organization_id: number | null;
  person_id: number | null;
  deal_id: number | null;
  error: string | null;
};

export type ExportResponse = {
  created: number;
  skipped: number;
  failed: number;
  items: ExportResultItem[];
};
