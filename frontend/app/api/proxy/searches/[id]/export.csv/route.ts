/**
 * CSV export endpoint — fetches all prospects for a search and streams a CSV
 * back to the browser. The bearer token stays server-side.
 */

import { NextResponse } from "next/server";

import { auth } from "@/auth";
import type { Prospect } from "@/lib/api";

export const dynamic = "force-dynamic";

const API_BASE = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

const HEADERS: (keyof Prospect)[] = [
  "name",
  "legal_name",
  "siren",
  "naf_code",
  "city",
  "postal_code",
  "phone_e164",
  "website",
  "score",
  "label",
  "rating",
  "reviews_count",
  "revenue_eur",
  "profit_eur",
  "financials_year",
  "director_name",
  "facebook_url",
  "instagram_url",
  "linkedin_url",
];

function csvEscape(value: unknown): string {
  if (value === null || value === undefined) return "";
  const s = String(value);
  if (/[",\n]/.test(s)) return `"${s.replace(/"/g, '""')}"`;
  return s;
}

export async function GET(
  _request: Request,
  context: { params: Promise<{ id: string }> },
): Promise<Response> {
  const session = await auth();
  if (!session?.accessToken) {
    return NextResponse.json({ detail: "Unauthorized" }, { status: 401 });
  }
  const { id } = await context.params;

  const upstream = await fetch(`${API_BASE}/api/v1/searches/${id}/prospects`, {
    headers: { Authorization: `Bearer ${session.accessToken}` },
    cache: "no-store",
  });
  if (!upstream.ok) {
    return NextResponse.json(
      { detail: `Upstream error: ${upstream.status}` },
      { status: upstream.status },
    );
  }
  const prospects = (await upstream.json()) as Prospect[];

  const rows = [
    HEADERS.join(","),
    ...prospects.map((p) => HEADERS.map((h) => csvEscape(p[h])).join(",")),
  ];
  const body = rows.join("\n");

  return new Response(body, {
    status: 200,
    headers: {
      "Content-Type": "text/csv; charset=utf-8",
      "Content-Disposition": `attachment; filename="noxiasprospect-${id}.csv"`,
    },
  });
}
