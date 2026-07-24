"use client";

import Link from "next/link";
import { useEffect, useState } from "react";

type Stats = {
  emails_total: number;
  pending: number;
  matched: number;
  partial: number;
  not_found: number;
  failed: number;
  completed: number;
  success_rate: number;
};

type Contact = {
  id: string;
  email: string;
  domain: string;
  phone: string | null;
  confidence: number | null;
  status: string;
  created_at: string;
};

type ContactsResponse = {
  items: Contact[];
};

const API_URL =
  process.env.NEXT_PUBLIC_API_URL ?? "http://127.0.0.1:8000";

function formatNumber(value: number): string {
  return new Intl.NumberFormat("sl-SI").format(value);
}

const PUBLIC_EMAIL_DOMAINS = new Set([
  "gmail.com", "googlemail.com", "outlook.com", "hotmail.com",
  "live.com", "msn.com", "yahoo.com", "icloud.com", "me.com",
  "mac.com", "aol.com", "proton.me", "protonmail.com",
  "gmx.com", "gmx.net", "mail.com", "zoho.com",
  "telemach.net", "siol.net",
]);

function getDisplayStatus(contact: Contact): string {
  if (contact.phone) return "MATCHED";

  if (
    ["PARTIAL_MATCH", "NOT_FOUND", "EMAIL_FOUND", "SKIPPED_FREE_EMAIL"].includes(contact.status) ||
    (contact.status === "FAILED" && PUBLIC_EMAIL_DOMAINS.has(contact.domain.toLowerCase()))
  ) {
    return "NO_PHONE";
  }

  return contact.status;
}

function getStatusLabel(status: string): string {
  const labels: Record<string, string> = {
    NEW: "Čaka",
    MATCHED: "Telefon najden",
    NO_PHONE: "Brez telefona",
    FAILED: "Napaka",
  };

  return labels[status] ?? status;
}

function getStatusClass(status: string): string {
  const classes: Record<string, string> = {
    NEW: "statusNew",
    MATCHED: "statusMatched",
    NO_PHONE: "statusNotFound",
    FAILED: "statusFailed",
  };

  return classes[status] ?? "";
}

export default function Home() {
  const [stats, setStats] = useState<Stats | null>(null);
  const [contacts, setContacts] = useState<Contact[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  async function loadDashboard() {
    try {
      setLoading(true);
      setError(null);

      const [statsResponse, contactsResponse] = await Promise.all([
        fetch(`${API_URL}/stats`, {
          cache: "no-store",
        }),
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
      const contactsData: ContactsResponse =
        await contactsResponse.json();

      setStats(statsData);
      setContacts(contactsData.items);
    } catch (err) {
      setError(
        err instanceof Error
          ? err.message
          : "Pri nalaganju podatkov je prišlo do napake.",
      );
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    void loadDashboard();
  }, []);

  const statCards = [
    {
      label: "Vsi e-maili",
      value: stats?.emails_total ?? 0,
      helper: "Vsi kontakti v bazi",
    },
    {
      label: "Čaka na obdelavo",
      value: stats?.pending ?? 0,
      helper: "Status NEW",
    },
    {
      label: "Telefon najden",
      value: stats?.matched ?? 0,
      helper: "Kontakti z najdeno številko",
    },
    {
      label: "Brez telefona",
      value: (stats?.partial ?? 0) + (stats?.not_found ?? 0),
      helper: "Telefon ni bil najden",
    },
    {
      label: "Napake",
      value: stats?.failed ?? 0,
      helper: "Dejanske tehnične napake",
    },
    {
      label: "Uspešnost",
      value: `${stats?.success_rate ?? 0}%`,
      helper: `${formatNumber(stats?.completed ?? 0)} obdelanih`,
    },
  ];

  return (
    <>
      <header className="pageHeader">
        <div>
          <p className="eyebrow">INTERNO ORODJE</p>
          <h1>Pregled kontaktov</h1>
          <p className="muted">
            Poišči javno objavljene telefonske številke za e-maile
            v bazi.
          </p>
        </div>

        <div className="headerActions">
          <button
            className="secondaryButton"
            type="button"
            onClick={() => void loadDashboard()}
            disabled={loading}
          >
            Osveži podatke
          </button>

          <button type="button" disabled>
            Začni obogatitev
          </button>
        </div>
      </header>

      {error && (
        <div className="alert alertError">
          <div>
            <strong>Podatkov ni bilo mogoče prikazati.</strong>
            <p>{error}</p>
          </div>

          <button
            type="button"
            className="smallButton"
            onClick={() => void loadDashboard()}
          >
            Poskusi znova
          </button>
        </div>
      )}

      <div className="stats statsSix">
        {statCards.map((stat) => (
          <article key={stat.label}>
            <span>{stat.label}</span>

            <strong>
              {loading
                ? "—"
                : typeof stat.value === "number"
                  ? formatNumber(stat.value)
                  : stat.value}
            </strong>

            <small>{stat.helper}</small>
          </article>
        ))}
      </div>

      <section className="panel">
        <div className="panelTop">
          <div>
            <h2>Zadnji kontakti</h2>
            <p className="muted">
              Zadnjih osem kontaktov, dodanih v bazo.
            </p>
          </div>

          <Link href="/contacts" className="textLink">
            Poglej vse kontakte
          </Link>
        </div>

        {loading ? (
          <div className="stateMessage">
            <div className="spinner" />
            <p>Nalaganje kontaktov …</p>
          </div>
        ) : contacts.length === 0 ? (
          <div className="stateMessage">
            <h3>Ni kontaktov</h3>
            <p>Najprej uvozi e-maile v bazo.</p>
          </div>
        ) : (
          <div className="tableWrapper">
            <table>
              <thead>
                <tr>
                  <th>E-mail</th>
                  <th>Domena</th>
                  <th>Telefon</th>
                  <th>Status</th>
                  <th>Confidence</th>
                </tr>
              </thead>

              <tbody>
                {contacts.map((contact) => (
                  <tr key={contact.id}>
                    <td>
                      <strong className="emailCell">
                        {contact.email}
                      </strong>
                    </td>

                    <td>{contact.domain}</td>

                    <td>{contact.phone ?? "—"}</td>

                    <td>
                      {(() => {
                        const displayStatus = getDisplayStatus(contact);

                        return (
                          <span
                            className={`statusBadge ${getStatusClass(
                              displayStatus,
                            )}`}
                          >
                            {getStatusLabel(displayStatus)}
                          </span>
                        );
                      })()}
                    </td>

                    <td>
                      {contact.confidence !== null
                        ? `${contact.confidence}%`
                        : "—"}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </section>
    </>
  );
}