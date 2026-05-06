import { auth } from "@/auth";
import { NextResponse } from "next/server";

/**
 * Protect all app routes except auth callbacks, the public landing page, and
 * the login page itself. Unauthenticated requests are redirected to /login,
 * preserving the original URL via `?callbackUrl=`.
 */
export default auth((req) => {
  const { pathname } = req.nextUrl;
  const isAuthRoute = pathname.startsWith("/api/auth");
  const isPublicRoute = pathname === "/" || pathname === "/login";

  if (isAuthRoute || isPublicRoute) {
    return NextResponse.next();
  }

  if (!req.auth) {
    const loginUrl = new URL("/login", req.url);
    loginUrl.searchParams.set("callbackUrl", pathname);
    return NextResponse.redirect(loginUrl);
  }

  return NextResponse.next();
});

export const config = {
  // Run the middleware on every route except static assets and Next internals.
  matcher: ["/((?!_next/static|_next/image|favicon.ico|.*\\.(?:svg|png|jpg|jpeg|gif|webp)$).*)"],
};
