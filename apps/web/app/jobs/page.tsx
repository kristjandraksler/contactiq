"use client";

import "./worker-center-styles.css";

import { useCallback, useEffect, useMemo, useState } from "react";

const API_URL =
  process.env.NEXT_PUBLIC_API_URL ??
  "http://127.0.0.1:8000";

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
  state: "paused" | "running" | "queued" | "completed" | "idle";
};

type WorkerJob = {
  id: string;
  domain: string;
  status: string;
  attempts: number;
  worker_id: string | null;
  started_at: string | null;
  finished_at: string | null;
  next_retry_at: string | null;
  last_error: string | null;
  processed_contacts: number | null;
  total_contacts: number | null;
  created_at: string;
  updated_at: string;
};

type WorkerCenterData = {
  worker: WorkerStatus;
  summary: {
    active_contacts: number;
    active_processed: number;
    queue_health_percent: number;
  };
  active_jobs: WorkerJob[];
  pending_jobs: WorkerJob[];
  failed_jobs: WorkerJob[];
  recent_jobs: WorkerJob[];
};

function formatNumber(value: number | null | undefined) {
  return new Intl.NumberFormat("sl-SI").format(value ?? 0);
}

function formatDate(value: string | null | undefined) {
  if (!value) return "—";

  return new Intl.DateTimeFormat("sl-SI", {
    dateStyle: "short",
    timeStyle: "short",
  }).format(new Date(value));
}

function jobProgress(job: WorkerJob) {
  const total = Number(job.total_contacts ?? 0);
  const processed = Number(job.processed_contacts ?? 0);

  if (total <= 0) return job.status === "MATCHED" || job.status === "NOT_FOUND" ? 100 : 0;

  return Math.min(100, Math.max(0, (processed / total) * 100));
}

function stateLabel(state: WorkerStatus["state"]) {
  if (state === "running") return "Worker deluje";
  if (state === "paused") return "Worker je ustavljen";
  if (state === "queued") return "Čakalna vrsta";
  if (state === "completed") return "Obdelava končana";
  return "Worker miruje";
}

export default function JobsPage() {
  const [data, setData] = useState<WorkerCenterData | null>(null);
  const [loading, setLoading] = useState(true);
  const [action, setAction] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(async (silent = false) => {
    try {
      if (!silent) setLoading(true);
      setError(null);

      const response = await fetch(
        `${API_URL}/admin/worker/center`,
        { cache: "no-store" },
      );

      const payload = (await response.json()) as
        | WorkerCenterData
        | { detail?: string };

      if (!response.ok) {
        throw new Error(
          "detail" in payload
            ? payload.detail ?? "Worker Center se ni naložil."
            : "Worker Center se ni naložil.",
        );
      }

      setData(payload as WorkerCenterData);
    } catch (err) {
      setError(
        err instanceof Error
          ? err.message
          : "Prišlo je do nepričakovane napake.",
      );
    } finally {
      if (!silent) setLoading(false);
    }
  }, []);

  useEffect(() => {
    void load();

    const timer = window.setInterval(() => {
      void load(true);
    }, 5000);

    return () => window.clearInterval(timer);
  }, [load]);

  async function callAction(
    name: string,
    path: string,
  ) {
    try {
      setAction(name);
      setError(null);

      const response = await fetch(
        `${API_URL}${path}`,
        {
          method: "POST",
          cache: "no-store",
        },
      );

      const payload = (await response.json()) as {
        detail?: string;
      };

      if (!response.ok) {
        throw new Error(
          payload.detail ?? "Dejanja ni bilo mogoče izvesti.",
        );
      }

      await load(true);
    } catch (err) {
      setError(
        err instanceof Error
          ? err.message
          : "Dejanja ni bilo mogoče izvesti.",
      );
    } finally {
      setAction(null);
    }
  }

  async function retryJob(jobId: string) {
    await callAction(
      `retry-${jobId}`,
      `/admin/worker/jobs/${jobId}/retry`,
    );
  }

  const worker = data?.worker;
  const activeJobs = data?.active_jobs ?? [];
  const pendingJobs = data?.pending_jobs ?? [];
  const failedJobs = data?.failed_jobs ?? [];
  const recentJobs = data?.recent_jobs ?? [];

  const state = worker?.state ?? "idle";

  const cards = useMemo(
    () => [
      {
        label: "Napredek",
        value: `${(worker?.progress_percent ?? 0).toFixed(1)}%`,
        detail: `${formatNumber(worker?.processed)} / ${formatNumber(worker?.total)} domen`,
      },
      {
        label: "V obdelavi",
        value: formatNumber(worker?.processing),
        detail: `${formatNumber(data?.summary.active_processed)} / ${formatNumber(data?.summary.active_contacts)} kontaktov`,
      },
      {
        label: "V čakalni vrsti",
        value: formatNumber(worker?.pending),
        detail: `${formatNumber(pendingJobs.length)} zadnjih prikazanih`,
      },
      {
        label: "Napake",
        value: formatNumber(worker?.failed),
        detail: `${formatNumber(failedJobs.length)} zahteva pregled`,
      },
    ],
    [
      data,
      failedJobs.length,
      pendingJobs.length,
      worker,
    ],
  );

  return (
    <div className="workerCenterPage">
      <header className="workerCenterHeader">
        <div>
          <p className="eyebrow">WORKER CENTER</p>
          <h1>Obdelava in čakalna vrsta</h1>
          <p className="muted">
            Spremljaj aktivne domene, upravljaj workerja in ponovno
            zaženi neuspešna opravila.
          </p>
        </div>

        <div className="workerCenterHeaderActions">
          <button
            type="button"
            className="secondaryButton"
            onClick={() => void load()}
            disabled={loading || action !== null}
          >
            {loading ? "Osvežujem…" : "Osveži"}
          </button>

          {worker?.paused ? (
            <button
              type="button"
              className="primaryButton"
              onClick={() =>
                void callAction(
                  "resume",
                  "/admin/worker/resume",
                )
              }
              disabled={action !== null}
            >
              {action === "resume" ? "Nadaljujem…" : "Nadaljuj worker"}
            </button>
          ) : (
            <button
              type="button"
              className="dangerButton"
              onClick={() =>
                void callAction(
                  "pause",
                  "/admin/worker/pause",
                )
              }
              disabled={action !== null}
            >
              {action === "pause" ? "Ustavljam…" : "Ustavi worker"}
            </button>
          )}
        </div>
      </header>

      {error && (
        <div className="workerErrorBanner">
          {error}
        </div>
      )}

      <section className="workerHero panel">
        <div>
          <span className={`workerStateDot ${state}`} />
          <div>
            <span className="workerSectionLabel">
              TRENUTNO STANJE
            </span>
            <h2>{stateLabel(state)}</h2>
            <p className="muted">
              Samodejna osvežitev vsakih 5 sekund.
            </p>
          </div>
        </div>

        <div className="workerHeroProgress">
          <strong>
            {(worker?.progress_percent ?? 0).toFixed(1)}%
          </strong>
          <span>zaključeno</span>
        </div>

        <div className="workerProgressTrack">
          <span
            style={{
              width: `${Math.min(
                100,
                worker?.progress_percent ?? 0,
              )}%`,
            }}
          />
        </div>
      </section>

      <section className="workerKpiGrid">
        {cards.map((card) => (
          <article className="workerKpiCard" key={card.label}>
            <span>{card.label}</span>
            <strong>{loading ? "—" : card.value}</strong>
            <small>{card.detail}</small>
          </article>
        ))}
      </section>

      <section className="workerControlBar panel">
        <div>
          <h2>Hitra dejanja</h2>
          <p className="muted">
            Upravljanje čakalne vrste brez PowerShella.
          </p>
        </div>

        <div>
          <button
            type="button"
            onClick={() =>
              void callAction(
                "seed",
                "/admin/worker/seed",
              )
            }
            disabled={action !== null}
          >
            {action === "seed" ? "Dodajam…" : "Sinhroniziraj queue"}
          </button>

          <button
            type="button"
            onClick={() =>
              void callAction(
                "stale",
                "/admin/worker/requeue-stale?stale_minutes=10",
              )
            }
            disabled={action !== null}
          >
            {action === "stale" ? "Vračam…" : "Requeue stale"}
          </button>

          <button
            type="button"
            onClick={() =>
              void callAction(
                "failed",
                "/admin/worker/retry-failed",
              )
            }
            disabled={action !== null}
          >
            {action === "failed" ? "Vračam…" : "Ponovi vse napake"}
          </button>
        </div>
      </section>

      <section className="workerMainGrid">
        <article className="panel workerTablePanel">
          <div className="workerPanelHeader">
            <div>
              <span className="workerSectionLabel">
                ACTIVE
              </span>
              <h2>Aktivna opravila</h2>
            </div>
            <span className="workerCountBadge">
              {formatNumber(activeJobs.length)}
            </span>
          </div>

          <div className="workerTableWrap">
            <table className="workerTable">
              <thead>
                <tr>
                  <th>Domena</th>
                  <th>Napredek</th>
                  <th>Kontakti</th>
                  <th>Poskusi</th>
                  <th>Začetek</th>
                </tr>
              </thead>
              <tbody>
                {activeJobs.length === 0 ? (
                  <tr>
                    <td colSpan={5} className="workerEmpty">
                      Trenutno ni aktivnih opravil.
                    </td>
                  </tr>
                ) : (
                  activeJobs.map((job) => {
                    const progress = jobProgress(job);

                    return (
                      <tr key={job.id}>
                        <td>
                          <strong>{job.domain}</strong>
                          <small>{job.worker_id ?? "Worker ni dodeljen"}</small>
                        </td>
                        <td>
                          <div className="workerJobProgress">
                            <span>
                              <i
                                style={{
                                  width: `${progress}%`,
                                }}
                              />
                            </span>
                            <strong>{progress.toFixed(0)}%</strong>
                          </div>
                        </td>
                        <td>
                          {formatNumber(job.processed_contacts)}
                          {" / "}
                          {formatNumber(job.total_contacts)}
                        </td>
                        <td>{formatNumber(job.attempts)}</td>
                        <td>{formatDate(job.started_at)}</td>
                      </tr>
                    );
                  })
                )}
              </tbody>
            </table>
          </div>
        </article>

        <article className="panel workerQueuePanel">
          <div className="workerPanelHeader">
            <div>
              <span className="workerSectionLabel">
                QUEUE
              </span>
              <h2>Naslednje domene</h2>
            </div>
            <span className="workerCountBadge">
              {formatNumber(worker?.pending)}
            </span>
          </div>

          <div className="workerQueueList">
            {pendingJobs.length === 0 ? (
              <div className="workerEmpty">
                Čakalna vrsta je prazna.
              </div>
            ) : (
              pendingJobs.slice(0, 10).map((job) => (
                <div className="workerQueueItem" key={job.id}>
                  <div>
                    <strong>{job.domain}</strong>
                    <span>
                      {formatNumber(job.total_contacts)} kontaktov
                    </span>
                  </div>
                  <span>Poskus {formatNumber(job.attempts)}</span>
                </div>
              ))
            )}
          </div>
        </article>
      </section>

      <section className="workerMainGrid">
        <article className="panel workerTablePanel">
          <div className="workerPanelHeader">
            <div>
              <span className="workerSectionLabel">
                FAILED
              </span>
              <h2>Neuspešna opravila</h2>
            </div>
            <span className="workerCountBadge danger">
              {formatNumber(failedJobs.length)}
            </span>
          </div>

          <div className="workerTableWrap">
            <table className="workerTable">
              <thead>
                <tr>
                  <th>Domena</th>
                  <th>Napaka</th>
                  <th>Poskusi</th>
                  <th>Posodobljeno</th>
                  <th />
                </tr>
              </thead>
              <tbody>
                {failedJobs.length === 0 ? (
                  <tr>
                    <td colSpan={5} className="workerEmpty">
                      Ni neuspešnih opravil.
                    </td>
                  </tr>
                ) : (
                  failedJobs.map((job) => (
                    <tr key={job.id}>
                      <td>
                        <strong>{job.domain}</strong>
                      </td>
                      <td className="workerErrorCell">
                        {job.last_error ?? "Neznana napaka"}
                      </td>
                      <td>{formatNumber(job.attempts)}</td>
                      <td>{formatDate(job.updated_at)}</td>
                      <td>
                        <button
                          type="button"
                          className="workerRetryButton"
                          onClick={() => void retryJob(job.id)}
                          disabled={action !== null}
                        >
                          {action === `retry-${job.id}`
                            ? "Vračam…"
                            : "Ponovi"}
                        </button>
                      </td>
                    </tr>
                  ))
                )}
              </tbody>
            </table>
          </div>
        </article>

        <article className="panel workerRecentPanel">
          <div className="workerPanelHeader">
            <div>
              <span className="workerSectionLabel">
                HISTORY
              </span>
              <h2>Zadnja opravila</h2>
            </div>
          </div>

          <div className="workerRecentList">
            {recentJobs.length === 0 ? (
              <div className="workerEmpty">
                Zgodovina je prazna.
              </div>
            ) : (
              recentJobs.slice(0, 12).map((job) => (
                <div className="workerRecentItem" key={job.id}>
                  <span
                    className={`workerJobStatus ${job.status.toLowerCase()}`}
                  >
                    {job.status.replaceAll("_", " ")}
                  </span>
                  <div>
                    <strong>{job.domain}</strong>
                    <small>{formatDate(job.updated_at)}</small>
                  </div>
                  <span>
                    {formatNumber(job.processed_contacts)}
                    {" / "}
                    {formatNumber(job.total_contacts)}
                  </span>
                </div>
              ))
            )}
          </div>
        </article>
      </section>
    </div>
  );
}
