import type { Metadata } from "next";
import "./globals.css";
import Sidebar from "@/components/Sidebar";

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
        <main className="shell">
          <Sidebar />
          <section className="content">{children}</section>
        </main>
      </body>
    </html>
  );
}
