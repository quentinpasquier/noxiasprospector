import NextAuth, { type DefaultSession, type NextAuthConfig } from "next-auth";
import Auth0Provider from "next-auth/providers/auth0";

declare module "next-auth" {
  /** Augment the session shape with the Auth0 access token. */
  interface Session {
    accessToken?: string;
    user: {
      id?: string;
    } & DefaultSession["user"];
  }

  /** Augment the JWT we persist in the cookie with the same fields. */
  interface JWT {
    accessToken?: string;
  }
}

export const AUTH_DISABLED = process.env.AUTH_DISABLED === "true";

const requiredEnv = (key: string): string => {
  const value = process.env[key];
  if (!value) {
    throw new Error(`Missing required environment variable: ${key}`);
  }
  return value;
};

/**
 * NextAuth v5 (Auth.js) configuration.
 *
 * - Default: a single Auth0 provider; the `audience` parameter ensures Auth0
 *   issues an *access token* for our FastAPI API instead of an opaque one,
 *   and we forward it as a `Bearer`.
 * - When `AUTH_DISABLED=true`: NextAuth is mounted with no providers so it
 *   neither crashes on missing Auth0 envs nor exposes a sign-in flow. The
 *   protected routes work because the backend is also in demo mode and
 *   resolves every request to a single `demo@noxias.fr` user.
 */
const config: NextAuthConfig = AUTH_DISABLED
  ? {
      providers: [],
      session: { strategy: "jwt" },
    }
  : {
      providers: [
        Auth0Provider({
          clientId: requiredEnv("AUTH0_CLIENT_ID"),
          clientSecret: requiredEnv("AUTH0_CLIENT_SECRET"),
          issuer: `https://${requiredEnv("AUTH0_DOMAIN")}`,
          authorization: {
            params: {
              audience: process.env.AUTH0_AUDIENCE,
              scope: "openid profile email",
            },
          },
        }),
      ],
      session: { strategy: "jwt" },
      pages: { signIn: "/login" },
      callbacks: {
        async jwt({ token, account }) {
          if (account?.access_token) {
            token.accessToken = account.access_token;
          }
          return token;
        },
        async session({ session, token }) {
          if (typeof token.accessToken === "string") {
            session.accessToken = token.accessToken;
          }
          if (typeof token.sub === "string") {
            session.user.id = token.sub;
          }
          return session;
        },
      },
    };

export const { handlers, signIn, signOut, auth } = NextAuth(config);
