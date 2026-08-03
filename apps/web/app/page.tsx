"use client";

import Link from "next/link";
import { FormEvent, useCallback, useEffect, useMemo, useState } from "react";
import { Icon } from "@/components/ui/Icon";

const API_URL = process.env.NEXT_PUBLIC_API_URL ?? "http://127.0.0.1:8000";

type CountryStat = { code: string; name: string | null; flag: string | null; count: number };
type Stats = {
  emails_total: number;
  business_contacts?: number;
  public_email?: number;
  pending: number;
  matched: number;
  partial: number;
  not_found: number;
  failed: number;
  completed: number;
  processed_total?: number;
  phones_found?: number;
  success_rate: number;
  completed_success_rate?: number;
  business_success_rate?: number;
  average_confidence?: number;
  person_phones?: number;
  company_phones?: number;
  countries?: CountryStat[];
  countries_total?: number;
};
type Contact = {
  id: string;
  email: string;
  domain: string;
  phone: string | null;
  confidence: number | null;
  status: string;
  created_at: string;
  updated_at?: string;
  country_code?: string | null;
  country_name?: string | null;
  country_flag?: string | null;
  person_match_type?: string | null;
};
type WorkerStatus = {
  pending: number;
  processing: number;
  matched: number;
  not_found: number;
  failed: number;
  total: number;
  processed: number;
  progress_percent: number;
  paused: boolean;
};
type EnrichmentResult = {
  status: string;
  phone: string | null;
  confidence: number | null;
  website: string | null;
  source_url: string | null;
  pages_scanned: number;
  scan_duration_ms: number;
  error: string | null;
  match_type?: string;
  person_name?: string | null;
};

function number(value: number | undefined) {
  return new Intl.NumberFormat("sl-SI").format(value ?? 0);
}

function timeAgo(value: string) {
  const diff = Date.now() - new Date(value).getTime();
  const min = Math.max(1, Math.round(diff / 60000));
  if (min < 60) return `${min} min ago`;
  const hours = Math.round(min / 60);
  if (hours < 24) return `${hours} h ago`;
  return `${Math.round(hours / 24)} d ago`;
}

function statusTone(status: string) {
  if (status === "MATCHED") return "success";
  if (status === "PUBLIC_EMAIL") return "violet";
  if (status === "FAILED") return "danger";
  return "neutral";
}

export default function DashboardPage() {
  const [stats, setStats] = useState<Stats | null>(null);
  const [contacts, setContacts] = useState<Contact[]>([]);
  const [worker, setWorker] = useState<WorkerStatus | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [query, setQuery] = useState("");
  const [lookup, setLookup] = useState<EnrichmentResult | null>(null);
  const [lookupLoading, setLookupLoading] = useState(false);
  const [lookupError, setLookupError] = useState<string | null>(null);

  const load = useCallback(async () => {
    try {
      setLoading(true);
      setError(null);
      const [statsRes, contactsRes, workerRes] = await Promise.all([
        fetch(`${API_URL}/stats`, { cache: "no-store" }),
        fetch(`${API_URL}/contacts?page=1&page_size=6&sort_by=updated_at&sort_direction=desc&status=MATCHED`, { cache: "no-store" }),
        fetch(`${API_URL}/admin/worker/status`, { cache: "no-store" }),
      ]);
      if (!statsRes.ok || !contactsRes.ok) throw new Error("Dashboard data could not be loaded.");
      const statsData = (await statsRes.json()) as Stats;
      const contactsData = (await contactsRes.json()) as { items: Contact[] };
      setStats(statsData);
      setContacts(contactsData.items ?? []);
      if (workerRes.ok) setWorker((await workerRes.json()) as WorkerStatus);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Unexpected dashboard error.");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => { void load(); }, [load]);

  async function submitLookup(event: FormEvent) {
    event.preventDefault();
    const value = query.trim();
    if (!value) return;
    try {
      setLookupLoading(true);
      setLookupError(null);
      setLookup(null);
      const url = value.includes("@")
        ? `${API_URL}/enrichment/person-test?email=${encodeURIComponent(value)}&force_refresh=true`
        : `${API_URL}/enrichment/test?domain=${encodeURIComponent(value)}&force_refresh=true`;
      const response = await fetch(url, { cache: "no-store" });
      const data = (await response.json()) as EnrichmentResult;
      if (!response.ok) throw new Error(data.error ?? "Lookup failed.");
      setLookup(data);
    } catch (err) {
      setLookupError(err instanceof Error ? err.message : "Lookup failed.");
    } finally {
      setLookupLoading(false);
    }
  }

  const countries = useMemo(() => (stats?.countries ?? []).slice(0, 6), [stats]);
  const maxCountry = Math.max(...countries.map((item) => item.count), 1);
  const success = stats?.business_success_rate ?? stats?.success_rate ?? 0;
  const progress = worker?.progress_percent ?? (
    stats?.processed_total && stats?.emails_total
      ? (stats.processed_total / stats.emails_total) * 100
      : 0
  );

  const workerState =
    worker?.paused
      ? "Paused"
      : (worker?.processing ?? 0) > 0
      ? "Running"
      : (worker?.pending ?? 0) > 0
      ? "Queued"
      : progress >= 100
      ? "Completed"
      : "Idle";

  const cards = [
    { label: "Total contacts", value: number(stats?.emails_total), detail: `${number(stats?.business_contacts)} business contacts`, icon: "contacts" as const, tone: "blue" },
    { label: "Phones found", value: number(stats?.phones_found), detail: `${number(stats?.person_phones)} personal · ${number(stats?.company_phones)} company`, icon: "phone" as const, tone: "green" },
    { label: "Success rate", value: `${success.toFixed(2)}%`, detail: `${number(stats?.business_contacts)} business contacts`, icon: "activity" as const, tone: "violet" },
    { label: "Countries", value: number(stats?.countries_total ?? countries.length), detail: `${number(stats?.public_email)} public-provider contacts`, icon: "globe" as const, tone: "orange" },
  ];

  return (
    <div className="v2Dashboard">
      <header className="v2Topbar">
        <div>
          <p className="v2Overline">CONTACT INTELLIGENCE</p>
          <h1>Good morning, Kristjan.</h1>
          <p>Here is what is happening across your contact database.</p>
        </div>
        <div className="v2TopbarActions">
          <button className="v2IconButton" type="button" onClick={() => void load()} aria-label="Refresh dashboard"><Icon name="refresh" width={17} /></button>
          <Link className="v2SecondaryButton" href="/import">Import contacts</Link>
          <Link className="v2PrimaryButton" href="/contacts">Open contacts <Icon name="arrow" width={16} /></Link>
        </div>
      </header>

      {error && <div className="v2ErrorBanner"><Icon name="warning" width={18}/><span>{error}</span></div>}

      <section className="v2KpiGrid">
        {cards.map((card) => (
          <article className="v2KpiCard" key={card.label}>
            <div className={`v2KpiIcon ${card.tone}`}><Icon name={card.icon} width={19}/></div>
            <div className="v2KpiMeta"><span>{card.label}</span><strong>{loading ? "—" : card.value}</strong><small>{card.detail}</small></div>
            <span className="v2KpiTrend">Live</span>
          </article>
        ))}
      </section>

      <section className="v2DashboardGrid">
        <article className="v2Panel v2WorkerPanel">
          <div className="v2PanelHead">
            <div><span className="v2PanelEyebrow">DISCOVERY ENGINE</span><h2>Worker status</h2></div>
            <span className={`v2StatusPill ${workerState.toLowerCase()}`}><i />{workerState}</span>
          </div>
          <div className="v2WorkerHero">
            <div className="v2ProgressRing" style={{ "--progress": `${Math.min(100, Math.max(0, progress)) * 3.6}deg` } as React.CSSProperties}>
              <div><strong>{progress.toFixed(1)}%</strong><span>processed</span></div>
            </div>
            <div className="v2WorkerStats">
              <div><span>Processed jobs</span><strong>{number(worker?.processed)} / {number(worker?.total)}</strong></div>
              <div><span>In progress</span><strong>{number(worker?.processing)}</strong></div>
              <div><span>Pending</span><strong>{number(worker?.pending ?? stats?.pending)}</strong></div>
              <div><span>Failed</span><strong>{number(worker?.failed ?? stats?.failed)}</strong></div>
            </div>
          </div>
          <div className="v2ProgressTrack"><span style={{ width: `${Math.min(100, progress)}%` }} /></div>
          <div className="v2PanelFooter"><span>Queue updates automatically from Render</span><Link href="/jobs">Manage worker <Icon name="arrow" width={14}/></Link></div>
        </article>

        <article className="v2Panel v2LookupPanel">
          <div className="v2PanelHead"><div><span className="v2PanelEyebrow">QUICK LOOKUP</span><h2>Find a business phone</h2></div><span className="v2EngineBadge"><i/>Engine online</span></div>
          <p className="v2PanelIntro">Enter an email address or company domain to run an immediate intelligence lookup.</p>
          <form className="v2LookupForm" onSubmit={submitLookup}>
            <div><Icon name="search" width={18}/><input value={query} onChange={(e) => setQuery(e.target.value)} placeholder="name@company.com" aria-label="Email or domain" /></div>
            <button type="submit" disabled={lookupLoading}>{lookupLoading ? "Searching…" : "Run lookup"}</button>
          </form>
          {lookupError && <div className="v2LookupMessage error">{lookupError}</div>}
          {lookup && (
            <div className={`v2LookupResult ${lookup.status === "MATCHED" ? "matched" : "empty"}`}>
              <span className="v2LookupResultIcon"><Icon name={lookup.status === "MATCHED" ? "check" : "warning"} width={18}/></span>
              <div><small>{lookup.status === "MATCHED" ? "Phone discovered" : lookup.status}</small><strong>{lookup.phone ?? "No phone found"}</strong><span>{lookup.confidence !== null ? `${lookup.confidence}% confidence` : `${lookup.pages_scanned} pages scanned`}</span></div>
              {lookup.source_url && <a href={lookup.source_url} target="_blank" rel="noreferrer">Source ↗</a>}
            </div>
          )}
          {!lookup && !lookupError && <div className="v2LookupEmpty"><Icon name="search" width={20}/><span>Public business data only. Results include source and confidence.</span></div>}
        </article>
      </section>

      <section className="v2DashboardGrid lower">
        <article className="v2Panel v2CountriesPanel">
          <div className="v2PanelHead"><div><span className="v2PanelEyebrow">GEOGRAPHY</span><h2>Contact activity by country</h2></div><Link href="/contacts">View all</Link></div>
          <div className="v2CountryList">
            {countries.length === 0 ? <div className="v2EmptyState">Country data will appear after processing.</div> : countries.map((country) => (
              <div className="v2CountryRow" key={country.code}>
                <div className="v2CountryName"><span>{country.flag ?? "🌍"}</span><div><strong>{country.name ?? country.code}</strong><small>{country.code}</small></div></div>
                <div className="v2CountryBar"><span style={{ width: `${(country.count / maxCountry) * 100}%` }}/></div>
                <strong>{number(country.count)}</strong>
              </div>
            ))}
          </div>
        </article>

        <article className="v2Panel v2ActivityPanel">
          <div className="v2PanelHead"><div><span className="v2PanelEyebrow">RECENT ACTIVITY</span><h2>Latest phone discoveries</h2></div><Link href="/contacts">Open contacts</Link></div>
          <div className="v2ActivityList">
            {contacts.length === 0 ? (
              <div className="v2EmptyState">Recent matched contacts will appear here.</div>
            ) : contacts.map((contact) => (
              <Link href={`/contacts?search=${encodeURIComponent(contact.email)}`} className="v2ActivityItem" key={contact.id}>
                <span className={`v2ActivityIcon ${statusTone(contact.status)}`}><Icon name={contact.status === "MATCHED" ? "phone" : contact.status === "PUBLIC_EMAIL" ? "globe" : "contacts"} width={16}/></span>
                <div><strong>{contact.email}</strong><span>{contact.phone ?? contact.domain}</span></div>
                <div className="v2ActivitySide"><span className={`v2MiniBadge ${statusTone(contact.status)}`}>{contact.status.replaceAll("_", " ")}</span><small>{timeAgo(contact.updated_at ?? contact.created_at)}</small></div>
              </Link>
            ))}
          </div>
        </article>
      </section>
    </div>
  );
}
