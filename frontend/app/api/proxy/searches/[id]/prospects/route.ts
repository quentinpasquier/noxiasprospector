/**
 * Proxy that forwards bearer-authenticated GET to the backend's
 * `/searches/{id}/prospects`. Used by the live-view client component to
 * refresh the prospects list while SSE updates progress.
 */

import { NextResponse } from "next/server";

import { auth } from "@/auth";

export const dynamic = "force-dynamic";

const API_BASE = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

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

  return new Response(upstream.body, {
    status: upstream.status,
    headers: { "Content-Type": "application/json" },
  });
}
