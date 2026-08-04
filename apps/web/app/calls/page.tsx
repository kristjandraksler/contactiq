"use client";

import "./calls.css";

import {
  FormEvent,
  useCallback,
  useEffect,
  useMemo,
  useState,
} from "react";

const API_URL =
  process.env.NEXT_PUBLIC_API_URL ??
  "http://127.0.0.1:8000";

type ContactInfo = {
  id: string;
  email: string;
  domain: string;
  website: string | null;
  phone: string | null;
  country_name: string | null;
  country_flag: string | null;
  confidence: number | null;
  person_match_type: string | null;
};

type CallLogItem = {
  id: string;
  contact_id: string;
  call_result: string;
  summary: string;
  next_action: string;
  next_call_at: string | null;
  duration_seconds: number | null;
  created_by: string | null;
  created_at: string;
  updated_at: string;
  email_targets: ContactInfo | ContactInfo[];
};

type ResponseData = {
  items: CallLogItem[];
  pagination: {
    page: number;
    page_size: number;
    total: number;
    total_pages: number;
    has_previous: boolean;
    has_next: boolean;
  };
  stats: {
    today: number;
    this_week: number;
    follow_up: number;
    meetings: number;
    no_answer: number;
    wrong_number: number;
  };
};

const RESULT_LABELS: Record<string, string> = {
  CONNECTED: "Pogovor",
  NO_ANSWER: "Ni odgovora",
  VOICEMAIL: "Govorna pošta",
  WRONG_NUMBER: "Napačna številka",
  NOT_INTERESTED: "Ne zanima",
  FOLLOW_UP: "Follow-up",
  MEETING_BOOKED: "Termin dogovorjen",
  OFFER_SENT: "Ponudba poslana",
  OTHER: "Drugo",
};

const ACTION_LABELS: Record<string, string> = {
  NONE: "Brez aktivnosti",
  CALL: "Ponovni klic",
  EMAIL: "Pošlji e-mail",
  MEETING: "Sestanek",
  OFFER: "Pošlji ponudbo",
  OTHER: "Drugo",
};

function contactOf(item: CallLogItem): ContactInfo | null {
  if (Array.isArray(item.email_targets)) {
    return item.email_targets[0] ?? null;
  }

  return item.email_targets ?? null;
}

function number(value: number | undefined) {
  return new Intl.NumberFormat("sl-SI").format(value ?? 0);
}

function date(value: string | null) {
  if (!value) return "—";

  return new Intl.DateTimeFormat("sl-SI", {
    dateStyle: "medium",
    timeStyle: "short",
  }).format(new Date(value));
}

function minutes(seconds: number | null) {
  if (seconds === null) return "—";
  return `${Math.max(1, Math.round(seconds / 60))} min`;
}

async function errorMessage(
  response: Response,
  fallback: string,
) {
  try {
    const data = await response.json();

    if (typeof data?.detail === "string") {
      return data.detail;
    }
  } catch {
    return fallback;
  }

  return fallback;
}

export default function CallLogPage() {
  const [data, setData] = useState<ResponseData | null>(null);
  const [page, setPage] = useState(1);
  const [period, setPeriod] = useState("all");
  const [result, setResult] = useState("");
  const [action, setAction] = useState("");
  const [searchInput, setSearchInput] = useState("");
  const [search, setSearch] = useState("");
  const [selected, setSelected] = useState<CallLogItem | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(async () => {
    try {
      setLoading(true);
      setError(null);

      const params = new URLSearchParams({
        page: String(page),
        page_size: "25",
        period,
      });

      if (result) params.set("call_result", result);
      if (action) params.set("next_action", action);
      if (search.trim()) params.set("search", search.trim());

      const response = await fetch(
        `${API_URL}/call-log?${params.toString()}`,
        { cache: "no-store" },
      );

      if (!response.ok) {
        throw new Error(
          await errorMessage(
            response,
            "The Call Log could not be loaded.",
          ),
        );
      }

      setData((await response.json()) as ResponseData);
    } catch (err) {
      setError(
        err instanceof Error
          ? err.message
          : "The Call Log could not be loaded.",
      );
    } finally {
      setLoading(false);
    }
  }, [action, page, period, result, search]);

  useEffect(() => {
    void load();
  }, [load]);

  function submitSearch(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setPage(1);
    setSearch(searchInput);
  }

  function clearFilters() {
    setPeriod("all");
    setResult("");
    setAction("");
    setSearch("");
    setSearchInput("");
    setPage(1);
  }

  const items = data?.items ?? [];
  const stats = data?.stats;

  const cards = useMemo(
    () => [
      {
        label: "Call today",
        value: number(stats?.today),
        detail: "Recorded today",
      },
      {
        label: "This week",
        value: number(stats?.this_week),
        detail: "All call summaries",
      },
      {
        label: "Follow-up",
        value: number(stats?.follow_up),
        detail: "Scheduled callbacks",
      },
      {
        label: "Agreed dates",
        value: number(stats?.meetings),
        detail: "Result: appointment",
      },
    ],
    [stats],
  );

  return (
    <div className="v2Dashboard callLogPage">
      <header className="v2Topbar callLogHeader">
        <div>
          <p className="eyebrow">CALL LOG</p>
          <h1>Called</h1>
          <p className="muted">
            Call history, conversation summaries and scheduled
follow-ups in one place.
          </p>
        </div>

        <a className="v2PrimaryButton callLogPrimaryLink" href="/phones">
          + New summary on your phone
        </a>
      </header>

      <section className="v2KpiGrid callLogStats">
        {cards.map((card, index) => (
          <article className="v2KpiCard callLogStatCard" key={card.label}>
            <span
              className={`v2KpiIcon ${
                ["blue", "violet", "green", "orange"][index] ?? "blue"
              }`}
              aria-hidden="true"
            >
              {["☎", "◷", "↻", "✓"][index] ?? "•"}
            </span>

            <div className="v2KpiMeta">
              <span>{card.label}</span>
              <strong>{loading ? "—" : card.value}</strong>
              <small>{card.detail}</small>
            </div>
          </article>
        ))}
      </section>

      <section className="v2Panel callLogPanel">
        <div className="v2PanelHead callLogToolbar">
          <div>
            <h2>All recorded calls</h2>
            <p className="muted">
              {number(data?.pagination.total)} records
            </p>
          </div>

          <form onSubmit={submitSearch} className="callLogFilters">
            <input
              type="search"
              value={searchInput}
              onChange={(event) =>
                setSearchInput(event.target.value)
              }
              placeholder="Phone, email, domain or summary"
            />

            <select
              value={period}
              onChange={(event) => {
                setPeriod(event.target.value);
                setPage(1);
              }}
            >
              <option value="all">All dates</option>
              <option value="today">Today</option>
              <option value="week">This week</option>
              <option value="month">This month</option>
            </select>

            <select
              value={result}
              onChange={(event) => {
                setResult(event.target.value);
                setPage(1);
              }}
            >
              <option value="">All results</option>
              {Object.entries(RESULT_LABELS).map(
                ([value, label]) => (
                  <option key={value} value={value}>
                    {label}
                  </option>
                ),
              )}
            </select>

            <select
              value={action}
              onChange={(event) => {
                setAction(event.target.value);
                setPage(1);
              }}
            >
              <option value="">All activities</option>
              {Object.entries(ACTION_LABELS).map(
                ([value, label]) => (
                  <option key={value} value={value}>
                    {label}
                  </option>
                ),
              )}
            </select>

            <button type="submit">Search</button>

            {(search || period !== "all" || result || action) && (
              <button
                type="button"
                className="callLogClear"
                onClick={clearFilters}
              >
                Clean
              </button>
            )}
          </form>
        </div>

        {error && (
          <div className="callLogError">{error}</div>
        )}

        {loading ? (
          <div className="stateMessage callLogEmpty">Loading calls...</div>
        ) : items.length === 0 ? (
          <div className="stateMessage callLogEmpty">
            There are no calls recorded for the selected filters.
          </div>
        ) : (
          <div className="modernTableWrapper callLogTableWrap">
            <table className="modernTable callLogTable">
              <thead>
                <tr>
                  <th>Date</th>
                  <th>Contact</th>
                  <th>Phone</th>
                  <th>Result</th>
                  <th>Summary</th>
                  <th>Next activity</th>
                  <th>Called</th>
                  <th />
                </tr>
              </thead>

              <tbody>
                {items.map((item) => {
                  const contact = contactOf(item);

                  return (
                    <tr key={item.id}>
                      <td>{date(item.created_at)}</td>

                      <td>
                        <strong>{contact?.email ?? "—"}</strong>
                        <small>
                          {contact?.country_flag ?? ""}
                          {" "}
                          {contact?.domain ?? ""}
                        </small>
                      </td>

                      <td>
                        {contact?.phone ? (
                          <a href={`tel:${contact.phone}`}>
                            {contact.phone}
                          </a>
                        ) : (
                          "—"
                        )}
                      </td>

                      <td>
                        <span
                          className={`callLogResult ${item.call_result.toLowerCase()}`}
                        >
                          {RESULT_LABELS[item.call_result] ??
                            item.call_result}
                        </span>
                      </td>

                      <td className="callLogSummaryCell">
                        {item.summary}
                      </td>

                      <td>
                        <strong>
                          {ACTION_LABELS[item.next_action] ??
                            item.next_action}
                        </strong>
                        <small>{date(item.next_call_at)}</small>
                      </td>

                      <td>
                        <strong>{item.created_by ?? "—"}</strong>
                        <small>{minutes(item.duration_seconds)}</small>
                      </td>

                      <td>
                        <button
                          type="button"
                          className="callLogOpen"
                          onClick={() => setSelected(item)}
                        >
                          Open
                        </button>
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        )}

        <div className="callLogPagination">
          <span>
            Stran {data?.pagination.page ?? 1} od{" "}
            {data?.pagination.total_pages ?? 0}
          </span>

          <div>
            <button
              type="button"
              disabled={!data?.pagination.has_previous || loading}
              onClick={() =>
                setPage((current) => Math.max(1, current - 1))
              }
            >
              Previous
            </button>

            <button
              type="button"
              disabled={!data?.pagination.has_next || loading}
              onClick={() => setPage((current) => current + 1)}
            >
              Next
            </button>
          </div>
        </div>
      </section>

      {selected && (
        <div
          className="callLogDrawerBackdrop"
          onMouseDown={(event) => {
            if (event.target === event.currentTarget) {
              setSelected(null);
            }
          }}
        >
          <aside className="callLogDrawer v2Panel">
            <header>
              <div>
                <p className="eyebrow">CALL SUMMARY</p>
                <h2>
                  {contactOf(selected)?.phone ?? "call"}
                </h2>
                <p className="muted">
                  {contactOf(selected)?.email ?? ""}
                </p>
              </div>

              <button
                type="button"
                onClick={() => setSelected(null)}
              >
                ×
              </button>
            </header>

            <div className="callLogDrawerBody">
              <div className="callLogDrawerMeta">
                <span>
                  {RESULT_LABELS[selected.call_result] ??
                    selected.call_result}
                </span>
                <span>{date(selected.created_at)}</span>
              </div>

              <section>
                <h3>Summary</h3>
                <p>{selected.summary}</p>
              </section>

              <section className="callLogDrawerGrid">
                <div>
                  <span>Next activity</span>
                  <strong>
                    {ACTION_LABELS[selected.next_action] ??
                      selected.next_action}
                  </strong>
                </div>

                <div>
                  <span>Follow-up date</span>
                  <strong>{date(selected.next_call_at)}</strong>
                </div>

                <div>
                  <span>Duration</span>
                  <strong>{minutes(selected.duration_seconds)}</strong>
                </div>

                <div>
                  <span>Called</span>
                  <strong>{selected.created_by ?? "—"}</strong>
                </div>
              </section>
            </div>
          </aside>
        </div>
      )}
    </div>
  );
}
