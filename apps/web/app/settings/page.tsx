"use client";

import { useEffect, useState } from "react";

type SystemInfo = {
  application: {
    name: string;
    version: string;
    environment: string;
  };
  services: {
    api: string;
    database: string;
    crawler: string;
    company_cache: string;
  };
  database: {
    provider: string;
    email_targets: number;
    companies: number;
  };
  enrichment: {
    website_crawler: boolean;
    company_cache: boolean;
    matched_ttl_days: number;
    not_found_ttl_days: number;
    statuses: string[];
  };
  stack: {
    frontend: string;
    backend: string;
    database: string;
    hosting_frontend: string;
    hosting_backend: string;
  };
};

const API_URL =
  process.env.NEXT_PUBLIC_API_URL ?? "http://127.0.0.1:8000";

function serviceLabel(value: string) {
  if (value === "online") return "Online";
  if (value === "connected") return "Povezano";
  if (value === "ready") return "Pripravljeno";
  if (value === "active") return "Aktivno";
  if (value === "disconnected") return "Ni povezave";
  return value;
}

function statusClass(value: string) {
  return value === "disconnected"
    ? "systemStatus systemStatusError"
    : "systemStatus systemStatusOk";
}

export default function SettingsPage() {
  const [data, setData] = useState<SystemInfo | null>(null);
  const [error, setError] = useState("");
  const [isLoading, setIsLoading] = useState(true);

  useEffect(() => {
    async function loadSystemInfo() {
      try {
        setIsLoading(true);
        setError("");

        const response = await fetch(`${API_URL}/system/info`, {
          cache: "no-store",
        });

        if (!response.ok) {
          throw new Error("Podatkov o sistemu ni bilo mogoče naložiti.");
        }

        const payload = (await response.json()) as SystemInfo;
        setData(payload);
      } catch (requestError) {
        setError(
          requestError instanceof Error
            ? requestError.message
            : "Prišlo je do nepričakovane napake.",
        );
      } finally {
        setIsLoading(false);
      }
    }

    void loadSystemInfo();
  }, []);

  return (
    <>
      <header>
        <div>
          <p className="eyebrow">NASTAVITVE</p>
          <h1>Konfiguracija sistema</h1>
          <p className="muted">
            Pregled dejanskega stanja storitev in konfiguracije ContactIQ.
          </p>
        </div>
      </header>

      {isLoading && (
        <section className="panel pagePanel">
          <div className="stateMessage largeState">
            <div className="spinner" />
            <p>Nalaganje podatkov o sistemu ...</p>
          </div>
        </section>
      )}

      {!isLoading && error && (
        <div className="alert alertError">
          <div>
            <strong>Podatkov ni bilo mogoče naložiti.</strong>
            <p>{error}</p>
          </div>
        </div>
      )}

      {!isLoading && data && (
        <>
          <section className="panel">
            <div className="panelTop">
              <div>
                <h2>Status sistema</h2>
                <p className="muted">
                  Trenutno stanje ključnih storitev ContactIQ.
                </p>
              </div>
            </div>

            <div className="settingsList">
              {[
                ["API", data.services.api],
                ["Supabase", data.services.database],
                ["Website Crawler", data.services.crawler],
                ["Company Cache", data.services.company_cache],
              ].map(([label, value]) => (
                <div className="settingsRow" key={label}>
                  <span>{label}</span>
                  <span className={statusClass(value)}>
                    <span className="statusDot" />
                    {serviceLabel(value)}
                  </span>
                </div>
              ))}
            </div>
          </section>

          <section className="settingsColumns">
            <article className="panel settingsCard">
              <div>
                <h2>Baza podatkov</h2>
                <p className="muted">
                  Osnovne informacije o podatkih v Supabase.
                </p>
              </div>

              <dl className="detailsList">
                <div>
                  <dt>Ponudnik</dt>
                  <dd>{data.database.provider}</dd>
                </div>
                <div>
                  <dt>Kontakti</dt>
                  <dd>{data.database.email_targets.toLocaleString("sl-SI")}</dd>
                </div>
                <div>
                  <dt>Podjetja v cacheu</dt>
                  <dd>{data.database.companies.toLocaleString("sl-SI")}</dd>
                </div>
              </dl>
            </article>

            <article className="panel settingsCard">
              <div>
                <h2>Enrichment</h2>
                <p className="muted">
                  Aktivna pravila za iskanje telefonskih številk.
                </p>
              </div>

              <dl className="detailsList">
                <div>
                  <dt>Website Crawler</dt>
                  <dd>{data.enrichment.website_crawler ? "Aktiven" : "Izklopljen"}</dd>
                </div>
                <div>
                  <dt>Company Cache</dt>
                  <dd>{data.enrichment.company_cache ? "Aktiven" : "Izklopljen"}</dd>
                </div>
                <div>
                  <dt>MATCHED cache</dt>
                  <dd>{data.enrichment.matched_ttl_days} dni</dd>
                </div>
                <div>
                  <dt>NOT_FOUND cache</dt>
                  <dd>{data.enrichment.not_found_ttl_days} dni</dd>
                </div>
              </dl>
            </article>

            <article className="panel settingsCard">
              <div>
                <h2>Sistem</h2>
                <p className="muted">
                  Informacije o aplikaciji in produkcijskem okolju.
                </p>
              </div>

              <dl className="detailsList">
                <div>
                  <dt>Aplikacija</dt>
                  <dd>{data.application.name}</dd>
                </div>
                <div>
                  <dt>Različica API</dt>
                  <dd>v{data.application.version}</dd>
                </div>
                <div>
                  <dt>Okolje</dt>
                  <dd>{data.application.environment}</dd>
                </div>
                <div>
                  <dt>Frontend</dt>
                  <dd>{data.stack.frontend} · {data.stack.hosting_frontend}</dd>
                </div>
                <div>
                  <dt>Backend</dt>
                  <dd>{data.stack.backend} · {data.stack.hosting_backend}</dd>
                </div>
              </dl>
            </article>

            <article className="panel settingsCard">
              <div>
                <h2>Statusi kontaktov</h2>
                <p className="muted">
                  Statusi, ki jih uporablja trenutni enrichment proces.
                </p>
              </div>

              <div className="statusPills">
                {data.enrichment.statuses.map((status) => (
                  <span className="statusBadge statusNew" key={status}>
                    {status}
                  </span>
                ))}
              </div>
            </article>
          </section>
        </>
      )}
    </>
  );
}