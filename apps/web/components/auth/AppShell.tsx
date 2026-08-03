"use client";

import { usePathname } from "next/navigation";

import Sidebar from "@/components/Sidebar";

export default function AppShell({
  children,
}: {
  children: React.ReactNode;
}) {
  const pathname = usePathname();

  if (pathname.startsWith("/login")) {
    return <main className="authOnlyShell">{children}</main>;
  }

  return (
    <main className="shell">
      <Sidebar />
      <section className="content">{children}</section>
    </main>
  );
}
