import type { Metadata } from "next";

import "./globals.css";

import AppShell from "@/components/auth/AppShell";
import AuthProvider from "@/components/auth/AuthProvider";

export const metadata: Metadata = {
  title: "ContactIQ — Contact Intelligence",
  description: "Poslovno orodje za iskanje in obogatitev kontaktov.",
};

export default function RootLayout({
  children,
}: Readonly<{ children: React.ReactNode }>) {
  return (
    <html lang="sl">
      <body>
        <AuthProvider>
          <AppShell>{children}</AppShell>
        </AuthProvider>
      </body>
    </html>
  );
}
