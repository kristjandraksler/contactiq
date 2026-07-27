"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";

const items = [
  { href: "/", label: "Pregled", icon: "⌂" },
  { href: "/contacts", label: "Kontakti", icon: "◎" },
  { href: "/phones", label: "Telefoni", icon: "↗" },
  { href: "/companies", label: "Podjetja", icon: "◇" },
  { href: "/jobs", label: "Opravila", icon: "✓" },
  { href: "/import", label: "Uvoz", icon: "↓" },
  { href: "/settings", label: "Nastavitve", icon: "⚙" },
];

export default function Sidebar() {
  const pathname = usePathname();

  return (
    <aside className="sidebar">
      <div className="sidebarTop">
        <Link href="/" className="brand">
          <span className="brandMark">C</span>
          <span className="brandText">
            Contact<strong>IQ</strong>
          </span>
        </Link>

        <div className="workspacePill">
          <span>Internal workspace</span>
          <i />
        </div>
      </div>

      <nav className="sidebarNav">
        <p>Workspace</p>
        {items.slice(0, 5).map((item) => {
          const active =
            item.href === "/"
              ? pathname === "/"
              : pathname.startsWith(item.href);

          return (
            <Link
              key={item.href}
              href={item.href}
              className={active ? "active" : ""}
            >
              <span className="navIcon">{item.icon}</span>
              {item.label}
            </Link>
          );
        })}

        <p className="navGroupLabel">Upravljanje</p>
        {items.slice(5).map((item) => {
          const active = pathname.startsWith(item.href);
          return (
            <Link
              key={item.href}
              href={item.href}
              className={active ? "active" : ""}
            >
              <span className="navIcon">{item.icon}</span>
              {item.label}
            </Link>
          );
        })}
      </nav>

      <div className="sidebarFooter">
        <div className="sidebarUsage">
          <div>
            <span>Mesečna poraba</span>
            <strong>V razvoju</strong>
          </div>
          <div className="usageTrack"><span /></div>
        </div>
        <div className="userCard">
          <span className="userAvatar">KD</span>
          <div>
            <strong>ContactIQ</strong>
            <small>Administrator</small>
          </div>
        </div>
      </div>
    </aside>
  );
}
