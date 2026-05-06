/**
 * Browser-side Sentry init. Loaded automatically by @sentry/nextjs at the
 * start of every page.
 *
 * Default PII send-mode is OFF (sendDefaultPii: false) — we don't ship Auth0
 * tokens or prospect phone numbers to Sentry by accident.
 */

import * as Sentry from "@sentry/nextjs";

const dsn = process.env.NEXT_PUBLIC_SENTRY_DSN;

if (dsn) {
  Sentry.init({
    dsn,
    environment: process.env.NEXT_PUBLIC_SENTRY_ENVIRONMENT ?? "development",
    sendDefaultPii: false,
    tracesSampleRate: 0.05,
  });
}
