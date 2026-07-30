"use client";

import Link from "next/link";
import { FormEvent, useEffect, useMemo, useState } from "react";

import {
  getDisplayStatus,
  getStatusClass,
  getStatusLabel,
  isPublicEmailDomain,
} from "./contacts/utils";

type CountryStat = {
  code: string;
  name: string | null;
  flag: string | null;
  count: number;
};

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
  success_rate: number;
  business_success_rate?: number;
  average_confidence?: number;
  person_phones?: number;
  company_phones?: number;
  countries?: CountryStat[];
  countries_total?: number;
  unknown_country?: number;
};

type Contact = {
  id: string;
  email: string;
  domain: string;
  phone: string | null;
  confidence: number | null;
  status: string;
  created_at: string;
  country_code?: string | null;
  country_name?: string | null;
  country_flag?: string | null;
  country_confidence?: number | null;
};

type ContactsResponse = {
  items: Contact[];
  pagination?: {
    page: number;
    total_pages: number;
  };
};

type Candidate = {
  phone: string;
  score: number;
  source_url: string;
  source: string;
  occurrences: number;
  from_tel_link: boolean;
  source_diversity: number;
  page_diversity: number;
  evidence: string[];
  confidence?: number | null;
  confidence_label?: string;
  evidence_strength?: number;
  strengths?: string[] | null;
  warnings?: string[] | null;
  person_name?: string | null;
};

type EnrichmentResult = {
  status: string;
  website: string | null;
  phone: string | null;
  confidence: number | null;
  source_url: string | null;
  pages_scanned: number;
  scan_duration_ms: number;
  candidates: Candidate[];
  error: string | null;
  confidence_label?: string;
  cached?: boolean;
  force_refresh?: boolean;
  match_type?: "person" | "company" | "none";
  person_name?: string | null;
};

type SearchStep = {
  label: string;
  state: "waiting" | "active" | "done";
};

const API_URL =
  process.env.NEXT_PUBLIC_API_URL ?? "http://127.0.0.1:8000";

const initialSteps: SearchStep[] = [
  { label: "Prepoznavam e-mail in domeno", state: "waiting" },
  { label: "Odpiram spletno stran podjetja", state: "waiting" },
  { label: "Pregledujem kontaktne strani", state: "waiting" },
  { label: "Razvrščam telefonske kandidate", state: "waiting" },
  { label: "Izračunavam zanesljivost", state: "waiting" },
];

function formatNumber(value: number): string {
  return new Intl.NumberFormat("sl-SI").format(value);
}

function formatPhone(value: string | null): string {
  if (!value) return "—";
  return value.replace(/(\+\d{2,3})(\d{3})(\d{3})(\d+)/, "$1 $2 $3 $4");
}

function formatDuration(milliseconds: number): string {
  if (milliseconds < 1000) return `${milliseconds} ms`;
  return `${(milliseconds / 1000).toFixed(1)} s`;
}

function sourceLabel(source: string): string {
  const labels: Record<string, string> = {
    visible_text: "Besedilo strani",
    footer: "Noga strani",
    tel_link: "Telefonska povezava",
    schema_org: "Strukturirani podatki",
    microdata: "Meta podatki",
    person_block: "Osebni kontakt",
  };

  return labels[source] ?? source.replaceAll("_", " ");
}

function evidenceLabel(value: string): string {
  if (value === "exact_email") return "Točen e-mail osebe";
  if (value === "phone_near_email") return "Telefon neposredno ob e-mailu";
  if (value === "full_name") return "Ujemanje imena in priimka";
  if (value === "phone_near_name") return "Telefon neposredno ob imenu";
  if (value.startsWith("direction:")) return "Kontakt v istem vsebinskem bloku";
  if (value.startsWith("distance:")) return "Zelo bližnja povezava podatkov";
  if (value.startsWith("positive_context:")) {
    return `Blizu oznake »${value.split(":")[1]}«`;
  }
  if (value.startsWith("negative_context:")) {
    return `Opozorilo: ${value.split(":")[1]}`;
  }
  if (value.startsWith("source:")) {
    return sourceLabel(value.split(":")[1]);
  }
  if (value === "page:contact_page") return "Kontaktna stran";
  if (value === "page:homepage") return "Domača stran";
  if (value === "page:other_page") return "Notranja stran";
  if (value.startsWith("repeated_on_")) return "Ponovljeno na več straneh";
  if (value.startsWith("source_diversity:")) return "Več neodvisnih virov";
  return value.replaceAll("_", " ").replace("page:", "");
}

function confidenceTone(confidence: number | null): string {
  if (confidence === null) return "neutral";
  if (confidence >= 75) return "high";
  if (confidence >= 50) return "medium";
  return "low";
}

export default function Home() {
  const [stats, setStats] = useState<Stats | null>(null);
  const [contacts, setContacts] = useState<Contact[]>([]);
  const [dashboardLoading, setDashboardLoading] = useState(true);
  const [dashboardError, setDashboardError] = useState<string | null>(null);

  const [query, setQuery] = useState("zdenek@letko.net");
  const [searching, setSearching] = useState(false);
  const [searchError, setSearchError] = useState<string | null>(null);
  const [result, setResult] = useState<EnrichmentResult | null>(null);
  const [steps, setSteps] = useState<SearchStep[]>(initialSteps);

  async function loadDashboard() {
    try {
      setDashboardLoading(true);
      setDashboardError(null);

      const [statsResponse, contactsResponse] =
        await Promise.all([
          fetch(`${API_URL}/stats`, { cache: "no-store" }),
          fetch(`${API_URL}/contacts?page=1&page_size=8`, {
            cache: "no-store",
          }),
        ]);

      if (!statsResponse.ok) {
        throw new Error("Statistik ni bilo mogoče naložiti.");
      }
      if (!contactsResponse.ok) {
        throw new Error("Kontaktov ni bilo mogoče naložiti.");
      }

      const statsData: Stats = await statsResponse.json();
      const contactsData: ContactsResponse = await contactsResponse.json();
      setStats(statsData);
      setContacts(contactsData.items);
    } catch (error) {
      setDashboardError(
        error instanceof Error
          ? error.message
          : "Pri nalaganju podatkov je prišlo do napake.",
      );
    } finally {
      setDashboardLoading(false);
    }
  }

  useEffect(() => {
    void loadDashboard();
  }, []);

  async function animateSearchSteps() {
    for (let index = 0; index < initialSteps.length; index += 1) {
      setSteps((current) =>
        current.map((step, stepIndex) => ({
          ...step,
          state:
            stepIndex < index
              ? "done"
              : stepIndex === index
                ? "active"
                : "waiting",
        })),
      );
      await new Promise((resolve) => window.setTimeout(resolve, 260));
    }
  }

  async function handleLookup(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();

    const trimmedQuery = query.trim();
    if (!trimmedQuery) {
      setSearchError("Vpiši e-mail naslov ali domeno.");
      return;
    }

    try {
      setSearching(true);
      setSearchError(null);
      setResult(null);
      setSteps(initialSteps);

      const animation = animateSearchSteps();
      const lookupUrl = trimmedQuery.includes("@")
        ? `${API_URL}/enrichment/person-test?email=${encodeURIComponent(trimmedQuery)}&force_refresh=true`
        : `${API_URL}/enrichment/test?domain=${encodeURIComponent(trimmedQuery)}&force_refresh=true`;

      const response = await fetch(lookupUrl, {
        cache: "no-store",
      });

      const data = (await response.json()) as EnrichmentResult;
      await animation;

      setSteps((current) =>
        current.map((step) => ({ ...step, state: "done" })),
      );

      if (!response.ok) {
        throw new Error(data.error ?? "Iskanje ni uspelo.");
      }

      setResult(data);
    } catch (error) {
      setSearchError(
        error instanceof Error ? error.message : "Iskanje ni uspelo.",
      );
    } finally {
      setSearching(false);
    }
  }

  const realFailures = stats?.failed ?? 0;
  const withoutPhone =
    (stats?.partial ?? 0) +
    (stats?.not_found ?? 0);

  const metricCards = [
    {
      label: "Poslovni kontakti",
      value: stats?.business_contacts ?? 0,
      helper: "Kontakti brez javnih e-mail ponudnikov",
      icon: "users",
    },
    {
      label: "Javni e-maili",
      value: stats?.public_email ?? 0,
      helper: "Gmail, Hotmail, Yahoo in podobni",
      icon: "globe",
    },
    {
      label: "Najdeni telefoni",
      value: stats?.matched ?? 0,
      helper: `${formatNumber(stats?.person_phones ?? 0)} osebnih · ${formatNumber(stats?.company_phones ?? 0)} podjetniških`,
      icon: "phone",
    },
    {
      label: "Uspešnost",
      value: `${stats?.business_success_rate ?? stats?.success_rate ?? 0}%`,
      helper: `${formatNumber(stats?.completed ?? 0)} obdelanih poslovnih kontaktov`,
      icon: "chart",
    },
    {
      label: "Povp. confidence",
      value: `${stats?.average_confidence ?? 0}%`,
      helper: `${formatNumber(withoutPhone)} brez telefona · ${formatNumber(realFailures)} napak`,
      icon: "spark",
    },
  ];

  const bestCandidate = result?.candidates?.[0] ?? null;
  const confidence = result?.confidence ?? 0;
  const domainName = useMemo(() => {
    if (!result?.website) return query.split("@").pop() ?? query;
    try {
      return new URL(result.website).hostname.replace(/^www\./, "");
    } catch {
      return result.website;
    }
  }, [query, result?.website]);

  return (
    <div className="dashboardPage">
      <header className="dashboardHeader">
        <div>
          <p className="eyebrow">CONTACT INTELLIGENCE</p>
          <h1>Poišči pravi poslovni kontakt.</h1>
          <p className="dashboardLead">
            Iz e-mail naslova v nekaj sekundah poišči javno objavljeno
            telefonsko številko in preveri kakovost zadetka.
          </p>
        </div>

        <div className="headerActions">
          <button
            className="iconButton"
            type="button"
            onClick={() => void loadDashboard()}
            disabled={dashboardLoading}
            aria-label="Osveži podatke"
          >
            ↻
          </button>
          <Link href="/import" className="primaryLinkButton">
            Uvozi kontakte
          </Link>
        </div>
      </header>

      <section className="lookupHero">
        <div className="lookupGlow lookupGlowOne" />
        <div className="lookupGlow lookupGlowTwo" />

        <div className="lookupCopy">
          <span className="livePill">
            <span /> Phone Engine online
          </span>
          <h2>En e-mail. En preverjen kontakt.</h2>
          <p>
            ContactIQ pregleda spletno stran podjetja, razvrsti vse najdene
            številke in izbere najverjetnejši poslovni kontakt.
          </p>
        </div>

        <form className="lookupForm" onSubmit={handleLookup}>
          <label htmlFor="contact-query">E-mail naslov ali domena</label>
          <div className="lookupInputRow">
            <div className="lookupInputWrap">
              <span className="inputIcon">@</span>
              <input
                id="contact-query"
                value={query}
                onChange={(event) => setQuery(event.target.value)}
                placeholder="ime@podjetje.si"
                autoComplete="email"
              />
            </div>
            <button className="lookupButton" type="submit" disabled={searching}>
              {searching ? "Iščem …" : "Poišči kontakt"}
              {!searching && <span>→</span>}
            </button>
          </div>
          <p className="lookupHint">
            Uporabljamo samo javno dostopne poslovne podatke.
          </p>
        </form>
      </section>

      {searchError && (
        <div className="alert alertError modernAlert">
          <div>
            <strong>Iskanje ni uspelo.</strong>
            <p>{searchError}</p>
          </div>
        </div>
      )}

      {searching && (
        <section className="searchProgressCard">
          <div className="progressHeader">
            <div>
              <p className="eyebrow">ANALIZA V TEKU</p>
              <h2>Iščem najboljši kontakt</h2>
            </div>
            <div className="pulseOrb" />
          </div>

          <div className="searchSteps">
            {steps.map((step, index) => (
              <div className={`searchStep ${step.state}`} key={step.label}>
                <span className="stepIcon">
                  {step.state === "done"
                    ? "✓"
                    : step.state === "active"
                      ? "·"
                      : index + 1}
                </span>
                <span>{step.label}</span>
              </div>
            ))}
          </div>
        </section>
      )}

      {result && (
        <section className="resultSection">
          <div className="resultMainCard">
            <div className="resultTopline">
              <div>
                <span className={`resultStatus ${result.status.toLowerCase()}`}>
                  <span />{" "}
                  {result.status === "MATCHED"
                    ? result.match_type === "person"
                      ? "Osebni kontakt najden"
                      : "Kontakt podjetja najden"
                    : result.status}
                </span>
                <h2>{domainName}</h2>
                <a href={result.website ?? "#"} target="_blank" rel="noreferrer">
                  {result.website ?? "Spletna stran ni na voljo"}
                </a>
              </div>
              <div
                className={`confidenceRing ${confidenceTone(result.confidence)}`}
                style={{
                  background: `conic-gradient(${result.confidence !== null && result.confidence >= 75 ? "#27b47e" : result.confidence !== null && result.confidence < 50 ? "#e49a2f" : "#7d6cff"} ${confidence}%, #ececf2 0)`,
                }}
              >
                <strong>{result.confidence ?? 0}%</strong>
                <span>Zanesljivost</span>
              </div>
            </div>

            <div className="phoneHeroValue">
              <span>
                {result.match_type === "person"
                  ? `Osebni kontakt${result.person_name ? ` · ${result.person_name}` : ""}`
                  : "Najboljši zadetek"}
              </span>
              <strong>{formatPhone(result.phone)}</strong>
              {result.phone && (
                <button
                  type="button"
                  className="copyPhoneButton"
                  onClick={() => void navigator.clipboard.writeText(result.phone ?? "")}
                >
                  Kopiraj
                </button>
              )}
            </div>

            <div className="confidenceTrack" aria-hidden="true">
              <span style={{ width: `${Math.max(4, confidence)}%` }} />
            </div>

            <div className="resultMetrics">
              <div>
                <span>Vir</span>
                <strong>{bestCandidate ? sourceLabel(bestCandidate.source) : "—"}</strong>
              </div>
              <div>
                <span>Pregledane strani</span>
                <strong>{result.pages_scanned}</strong>
              </div>
              <div>
                <span>Čas analize</span>
                <strong>{formatDuration(result.scan_duration_ms)}</strong>
              </div>
              <div>
                <span>Kandidati</span>
                <strong>{result.candidates.length}</strong>
              </div>
            </div>
          </div>

          <aside className="evidenceCard">
            <div className="sectionHeading compactHeading">
              <div>
                <p className="eyebrow">RAZLAGA REZULTATA</p>
                <h2>Zakaj ta številka?</h2>
              </div>
            </div>

            <div className="evidenceList">
              {(bestCandidate?.strengths ?? []).map((strength) => (
                <div className="evidenceItem positive" key={strength}>
                  <span>✓</span>
                  <p>{strength}</p>
                </div>
              ))}
              {(bestCandidate?.warnings ?? []).map((warning) => (
                <div className="evidenceItem warning" key={warning}>
                  <span>!</span>
                  <p>{warning}</p>
                </div>
              ))}
              {!bestCandidate?.strengths?.length &&
                !bestCandidate?.warnings?.length && (
                  <p className="emptyEvidence">Za ta rezultat ni dodatne razlage.</p>
                )}
            </div>
          </aside>
        </section>
      )}

      {result && result.candidates.length > 0 && (
        <section className="candidateSection">
          <div className="sectionHeading">
            <div>
              <p className="eyebrow">CANDIDATE ANALYSIS</p>
              <h2>Primerjava kandidatov</h2>
              <p>Pregled vseh najverjetnejših številk, ki jih je našel sistem.</p>
            </div>
          </div>

          <div className="candidateGrid">
            {result.candidates.map((candidate, index) => (
              <article
                className={`candidateCard ${index === 0 ? "bestCandidate" : ""}`}
                key={`${candidate.phone}-${index}`}
              >
                <div className="candidateHeader">
                  <span>{index === 0
                    ? candidate.source === "person_block"
                      ? "Osebni kontakt"
                      : "Najboljši zadetek"
                    : `Alternativa ${index}`}</span>
                  <strong>Score {candidate.score}</strong>
                </div>
                <h3>{formatPhone(candidate.phone)}</h3>
                <div className="miniMetrics">
                  <span>{candidate.confidence ?? result.confidence ?? 0}% confidence</span>
                  <span>{sourceLabel(candidate.source)}</span>
                </div>
                <div className="badgeList">
                  {candidate.evidence.slice(0, 4).map((evidence) => (
                    <span
                      className={evidence.includes("negative") ? "warningBadge" : "evidenceBadge"}
                      key={evidence}
                    >
                      {evidenceLabel(evidence)}
                    </span>
                  ))}
                </div>
                <a href={candidate.source_url} target="_blank" rel="noreferrer">
                  Odpri vir ↗
                </a>
              </article>
            ))}
          </div>
        </section>
      )}

      <section className="metricsGrid">
        {metricCards.map((metric) => (
          <article className="metricCard" key={metric.label}>
            <div className={`metricIcon ${metric.icon}`}>
              {metric.icon === "phone"
                ? "↗"
                : metric.icon === "chart"
                  ? "%"
                  : metric.icon === "spark"
                    ? "✦"
                    : metric.icon === "globe"
                      ? "🌍"
                      : "◎"}
            </div>
            <div>
              <span>{metric.label}</span>
              <strong>
                {dashboardLoading
                  ? "—"
                  : typeof metric.value === "number"
                    ? formatNumber(metric.value)
                    : metric.value}
              </strong>
              <small>{metric.helper}</small>
            </div>
          </article>
        ))}
      </section>

      {dashboardError && (
        <div className="alert alertError modernAlert">
          <div>
            <strong>Pregleda ni bilo mogoče naložiti.</strong>
            <p>{dashboardError}</p>
          </div>
        </div>
      )}

      <section className="recentPanel">
        <div className="sectionHeading">
          <div>
            <p className="eyebrow">RECENT ACTIVITY</p>
            <h2>Zadnji kontakti</h2>
            <p>Najnovejši kontakti in trenutno stanje njihove obdelave.</p>
          </div>
          <Link href="/contacts" className="softLinkButton">
            Vsi kontakti →
          </Link>
        </div>

        {dashboardLoading ? (
          <div className="stateMessage modernState">
            <div className="spinner" />
            <p>Nalaganje kontaktov …</p>
          </div>
        ) : contacts.length === 0 ? (
          <div className="stateMessage modernState">
            <h3>Ni kontaktov</h3>
            <p>Najprej uvozi e-maile v bazo.</p>
          </div>
        ) : (
          <div className="modernTableWrapper">
            <table className="modernTable">
              <thead>
                <tr>
                  <th>Kontakt</th>
                  <th>Domena</th>
                  <th>Država</th>
                  <th>Telefon</th>
                  <th>Status</th>
                  <th>Confidence</th>
                </tr>
              </thead>
              <tbody>
                {contacts.map((contact) => {
                  const displayStatus = getDisplayStatus(
                    contact.status,
                    contact.phone,
                    contact.domain,
                  );

                  return (
                    <tr key={contact.id}>
                      <td>
                        <strong>{contact.email}</strong>
                        <small>Dodano v bazo</small>
                      </td>
                      <td>{contact.domain}</td>
                      <td>
                        {contact.country_code
                          ? `${contact.country_flag ?? "🌍"} ${contact.country_code}`
                          : "—"}
                      </td>
                      <td className="phoneCell">{formatPhone(contact.phone)}</td>
                      <td>
                        <span className={`statusBadge ${getStatusClass(displayStatus)}`}>
                          {getStatusLabel(displayStatus)}
                        </span>
                      </td>
                      <td>
                        <div className="tableConfidence">
                          <span>{contact.confidence !== null ? `${contact.confidence}%` : "—"}</span>
                          <div>
                            <i style={{ width: `${contact.confidence ?? 0}%` }} />
                          </div>
                        </div>
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        )}
      </section>
    </div>
  );
}
