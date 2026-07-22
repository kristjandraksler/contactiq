import Link from "next/link";

const items = [
  { href: "/", label: "Dashboard" },
  { href: "/contacts", label: "Kontakti" },
  { href: "/companies", label: "Podjetja" },
  { href: "/jobs", label: "Opravila" },
  { href: "/import", label: "Uvoz" },
  { href: "/settings", label: "Nastavitve" },
];

export default function Sidebar() {
  return (
    <aside className="sidebar">
      <div className="brand">Contact<span>IQ</span></div>
      <nav>
        {items.map((item) => (
          <Link key={item.href} href={item.href}>
            {item.label}
          </Link>
        ))}
      </nav>
    </aside>
  );
}
