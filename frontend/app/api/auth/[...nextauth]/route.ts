/**
 * NextAuth catch-all route for the Auth.js endpoints (`/api/auth/signin`,
 * `/api/auth/callback/auth0`, etc.).
 */
import { handlers } from "@/auth";

export const { GET, POST } = handlers;
