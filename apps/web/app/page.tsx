"use client";

import Link from "next/link";
import { useEffect, useState } from "react";

import { getDisplayStatus, getStatusClass, getStatusLabel, isPublicEmailDomain } from "./contacts/utils";

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
  pagination?: {
    page: number;
    total_pages: number;
  };
};

const API_URL =
  process.env.NEXT_PUBLIC_API_URL ?? "http://127.0.0.1:8000";

function formatNumber(value: number): string {
  return new Intl.NumberFormat("sl-SI").format(value);
}

export default function Home() {
  const [stats, setStats] = useState<Stats | null>(null);
  const [contacts, setContacts] = useState<Contact[]>([]);
  const [publicProviderFailures, setPublicProviderFailures] = useState(0);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  async function loadDashboard() {
    try {
      setLoading(true);
      setError(null);

      const [statsResponse, contactsResponse, failedContactsResponse] = await Promise.all([
        fetch(`${API_URL}/stats`, {
          cache: "no-store",
        }),
        fetch(`${API_URL}/contacts?page=1&page_size=8`, {
          cache: "no-store",
        }),
        fetch(`${API_URL}/contacts?page=1&page_size=250&status=FAILED`, {
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

      let publicFailureCount = 0;

      if (failedContactsResponse.ok) {
        const firstFailedPage: ContactsResponse =
          await failedContactsResponse.json();

        publicFailureCount += firstFailedPage.items.filter((contact) =>
          isPublicEmailDomain(contact.domain),
        ).length;

        const totalFailedPages = firstFailedPage.pagination?.total_pages ?? 1;

        if (totalFailedPages > 1) {
          const remainingPages = await Promise.all(
            Array.from({ length: totalFailedPages - 1 }, (_, index) =>
              fetch(
                `${API_URL}/contacts?page=${index + 2}&page_size=250&status=FAILED`,
                { cache: "no-store" },
              ),
            ),
          );

          for (const response of remainingPages) {
            if (!response.ok) continue;

            const pageData: ContactsResponse = await response.json();
            publicFailureCount += pageData.items.filter((contact) =>
              isPublicEmailDomain(contact.domain),
            ).length;
          }
        }
      }

      setStats(statsData);
      setContacts(contactsData.items);
      setPublicProviderFailures(publicFailureCount);
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

  const realFailures = Math.max(0, (stats?.failed ?? 0) - publicProviderFailures);
  const withoutPhone =
    (stats?.partial ?? 0) +
    (stats?.not_found ?? 0) +
    publicProviderFailures;

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
      value: withoutPhone,
      helper: "Telefon ni bil najden",
    },
    {
      label: "Napake",
      value: realFailures,
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
                        const displayStatus = getDisplayStatus(
                          contact.status,
                          contact.phone,
                          contact.domain,
                        );

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