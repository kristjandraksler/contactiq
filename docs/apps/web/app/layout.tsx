import type { Metadata } from "next";
import "./globals.css";
import Sidebar from "@/components/Sidebar";

export const metadata: Metadata = {
  title: "ContactIQ",
  description: "Interno orodje za obogatitev kontaktov",
};

export default function RootLayout({ children }: Readonly<{ children: React.ReactNode }>) {
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
