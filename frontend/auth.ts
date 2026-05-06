import NextAuth, { type DefaultSession } from "next-auth";
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

const requiredEnv = (key: string): string => {
  const value = process.env[key];
  if (!value) {
    throw new Error(`Missing required environment variable: ${key}`);
  }
  return value;
};

/**
 * NextAuth v5 (Auth.js) — single Auth0 provider with Google as a social
 * connection (configured Auth0-side). The `audience` parameter ensures Auth0
 * issues an *access token* targeted at our FastAPI API instead of an opaque
 * one; we forward it as a `Bearer` to the backend.
 */
export const { handlers, signIn, signOut, auth } = NextAuth({
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
});
