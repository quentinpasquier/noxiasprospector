/**
 * SSE proxy from the browser to the FastAPI `/searches/{id}/events` stream.
 *
 * The backend requires a Bearer token; the browser cannot hold one, so this
 * route reads the user's NextAuth session server-side, attaches the access
 * token, and pipes the upstream stream straight back to the client.
 */

import { NextResponse } from "next/server";

import { AUTH_DISABLED, auth } from "@/auth";

export const dynamic = "force-dynamic";

const API_BASE = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

export async function GET(
  _request: Request,
  context: { params: Promise<{ id: string }> },
): Promise<Response> {
  const headers: Record<string, string> = { Accept: "text/event-stream" };
  if (!AUTH_DISABLED) {
    const session = await auth();
    if (!session?.accessToken) {
      return NextResponse.json({ detail: "Unauthorized" }, { status: 401 });
    }
    headers.Authorization = `Bearer ${session.accessToken}`;
  }

  const { id } = await context.params;

  const upstream = await fetch(`${API_BASE}/api/v1/searches/${id}/events`, {
    headers,
    cache: "no-store",
  });

  if (!upstream.ok || !upstream.body) {
    return NextResponse.json(
      { detail: `Upstream error: ${upstream.status}` },
      { status: upstream.status },
    );
  }

  return new Response(upstream.body, {
    status: 200,
    headers: {
      "Content-Type": "text/event-stream",
      "Cache-Control": "no-cache",
      Connection: "keep-alive",
    },
  });
}
