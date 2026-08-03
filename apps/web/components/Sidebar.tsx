"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { Icon } from "./ui/Icon";

const primary = [
  { href: "/", label: "Dashboard", icon: "dashboard" as const },
  { href: "/contacts", label: "Contacts", icon: "contacts" as const },
  { href: "/companies", label: "Companies", icon: "company" as const },
  { href: "/phones", label: "Phone discovery", icon: "phone" as const },
  { href: "/jobs", label: "Worker", icon: "discovery" as const },
];

const secondary = [
  { href: "/import", label: "Import", icon: "import" as const },
  { href: "/settings", label: "Settings", icon: "settings" as const },
];

type NavItemProps = { href: string; label: string; icon: Parameters<typeof Icon>[0]["name"] };

function NavItem({ href, label, icon }: NavItemProps) {
  const pathname = usePathname();
  const active = href === "/" ? pathname === "/" : pathname.startsWith(href);

  return (
    <Link href={href} className={`v2NavItem ${active ? "active" : ""}`}>
      <Icon name={icon} width={18} height={18} />
      <span>{label}</span>
    </Link>
  );
}

export default function Sidebar() {
  return (
    <aside className="v2Sidebar">
      <div className="v2SidebarHead">
        <Link href="/" className="v2Brand">
          <span className="v2BrandMark">CI</span>
          <span>
            Contact<strong>IQ</strong>
          </span>
        </Link>
        <span className="v2Environment">Internal</span>
      </div>

      <nav className="v2Nav">
        <p>Workspace</p>
        {primary.map((item) => <NavItem key={item.href} {...item} />)}
        <p className="v2NavSection">Manage</p>
        {secondary.map((item) => <NavItem key={item.href} {...item} />)}
      </nav>

      <div className="v2SidebarFooter">
        <div className="v2UsageCard">
          <div className="v2UsageTop">
            <span>Database</span>
            <strong>Live</strong>
          </div>
          <div className="v2UsageTrack"><span /></div>
          <small>Contact intelligence workspace</small>
        </div>
        <div className="v2Profile">
          <span className="v2Avatar">KD</span>
          <div><strong>Administrator</strong><small>ContactIQ workspace</small></div>
        </div>
      </div>
    </aside>
  );
}
