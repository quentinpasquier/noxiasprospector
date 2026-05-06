import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "NoxiasProspect",
  description: "Outil interne de prospection commerciale B2B Noxias.",
  robots: { index: false, follow: false },
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}): JSX.Element {
  return (
    <html lang="fr">
      <body className="min-h-screen bg-background font-sans antialiased">
        {children}
      </body>
    </html>
  );
}
