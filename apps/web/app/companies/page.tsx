"use client";

import "./ui-v3.css";

import Link from "next/link";
import { useCallback, useEffect, useMemo, useState } from "react";

const API_URL = process.env.NEXT_PUBLIC_API_URL ?? "http://127.0.0.1:8000";

type Company = {
  domain: string;
  name: string;
  website: string | null;
  country_code: string | null;
  country_name: string | null;
  country_flag: string | null;
  contacts: number;
  phones: number;
  person_phones: number;
  company_phones: number;
  cross_border: number;
  success_rate: number;
  average_confidence: number;
  last_scan: string | null;
  is_public_provider: boolean;
};

type CompaniesResponse = {
  items: Company[];
  pagination: { page: number; page_size: number; total: number; total_pages: number; has_previous: boolean; has_next: boolean };
  summary: { companies: number; contacts: number; phones: number; countries: number };
};

function formatNumber(value: number) {
  return new Intl.NumberFormat("sl-SI").format(value);
}

function formatDate(value: string | null) {
  if (!value) return "—";
  return new Intl.DateTimeFormat("sl-SI", { dateStyle: "medium" }).format(new Date(value));
}

export default function CompaniesPage() {
  const [data, setData] = useState<CompaniesResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [search, setSearch] = useState("");
  const [country, setCountry] = useState("");
  const [hasPhone, setHasPhone] = useState("");
  const [page, setPage] = useState(1);

  const load = useCallback(async () => {
    try {
      setLoading(true);
      setError(null);
      const params = new URLSearchParams({ page: String(page), page_size: "25", sort_by: "contacts", sort_direction: "desc" });
      if (search.trim()) params.set("search", search.trim());
      if (country) params.set("country", country);
      if (hasPhone) params.set("has_phone", hasPhone);
      const response = await fetch(`${API_URL}/companies?${params}`, { cache: "no-store" });
      if (!response.ok) throw new Error("Podjetij ni bilo mogoče naložiti.");
      setData((await response.json()) as CompaniesResponse);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Nepričakovana napaka.");
    } finally {
      setLoading(false);
    }
  }, [country, hasPhone, page, search]);

  useEffect(() => { void load(); }, [load]);
  useEffect(() => { setPage(1); }, [search, country, hasPhone]);

  const countries = useMemo(() => {
    const map = new Map<string, { code: string; name: string; flag: string }>();
    for (const company of data?.items ?? []) {
      if (company.country_code) map.set(company.country_code, { code: company.country_code, name: company.country_name ?? company.country_code, flag: company.country_flag ?? "🌍" });
    }
    return [...map.values()].sort((a, b) => a.name.localeCompare(b.name));
  }, [data]);

  return (
    <div className="companiesV2Page ciDataPage ciCompaniesPage">
      <header className="companiesV2Header">
        <div><p className="eyebrow">COMPANY INTELLIGENCE</p><h1>Podjetja</h1><p className="muted">Združen pogled kontaktov, telefonov, držav in uspešnosti po domenah.</p></div>
        <Link className="primaryButton" href="/import">Uvozi kontakte</Link>
      </header>

      <section className="companiesKpis">
        <article><span>Podjetja</span><strong>{loading ? "—" : formatNumber(data?.summary.companies ?? 0)}</strong></article>
        <article><span>Kontakti</span><strong>{loading ? "—" : formatNumber(data?.summary.contacts ?? 0)}</strong></article>
        <article><span>Telefoni</span><strong>{loading ? "—" : formatNumber(data?.summary.phones ?? 0)}</strong></article>
        <article><span>Države</span><strong>{loading ? "—" : formatNumber(data?.summary.countries ?? 0)}</strong></article>
      </section>

      <section className="panel pagePanel companiesTablePanel">
        <div className="companiesToolbar">
          <div><h2>Seznam podjetij</h2><p className="muted">Klikni podjetje za podrobnosti, kontakte in vire.</p></div>
          <div className="companiesFilters">
            <input value={search} onChange={(e) => setSearch(e.target.value)} placeholder="Išči domeno ali podjetje" />
            <select value={country} onChange={(e) => setCountry(e.target.value)}><option value="">Vse države</option>{countries.map((item) => <option key={item.code} value={item.code}>{item.flag} {item.name}</option>)}</select>
            <select value={hasPhone} onChange={(e) => setHasPhone(e.target.value)}><option value="">Vsa podjetja</option><option value="true">S telefonom</option><option value="false">Brez telefona</option></select>
            <button type="button" onClick={() => void load()}>Osveži</button>
          </div>
        </div>

        {error && <div className="errorBanner">{error}</div>}
        <div className="companiesTableWrap">
          <table className="companiesTable">
            <thead><tr><th>Podjetje</th><th>Država</th><th>Kontakti</th><th>Telefoni</th><th>Uspešnost</th><th>Confidence</th><th>Zadnji pregled</th><th /></tr></thead>
            <tbody>
              {loading ? <tr><td colSpan={8} className="companiesEmpty">Nalagam podjetja …</td></tr> : (data?.items ?? []).length === 0 ? <tr><td colSpan={8} className="companiesEmpty">Ni podjetij za izbrane filtre.</td></tr> : data?.items.map((company) => (
                <tr key={company.domain}>
                  <td><div className="companyIdentity"><span className="companyAvatar">{company.name.slice(0, 2).toUpperCase()}</span><div><strong>{company.name}</strong><small>{company.domain}</small>{company.is_public_provider && <em>PUBLIC PROVIDER</em>}</div></div></td>
                  <td>{company.country_code ? <span>{company.country_flag ?? "🌍"} {company.country_name ?? company.country_code}</span> : <span className="muted">—</span>}</td>
                  <td><strong>{formatNumber(company.contacts)}</strong></td>
                  <td><strong>{formatNumber(company.phones)}</strong><small className="tableSubtext">{company.person_phones} osebnih · {company.company_phones} poslovnih</small></td>
                  <td><div className="successCell"><strong>{company.success_rate.toFixed(1)}%</strong><span><i style={{ width: `${Math.min(100, company.success_rate)}%` }} /></span></div></td>
                  <td>{company.average_confidence ? `${company.average_confidence.toFixed(0)}%` : "—"}</td>
                  <td>{formatDate(company.last_scan)}</td>
                  <td><Link className="companyOpenLink" href={`/companies/${encodeURIComponent(company.domain)}`}>Odpri →</Link></td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
        <div className="companiesPagination"><button disabled={!data?.pagination.has_previous} onClick={() => setPage((value) => Math.max(1, value - 1))}>← Prejšnja</button><span>Stran {data?.pagination.page ?? 1} od {data?.pagination.total_pages || 1}</span><button disabled={!data?.pagination.has_next} onClick={() => setPage((value) => value + 1)}>Naslednja →</button></div>
      </section>
    </div>
  );
}
