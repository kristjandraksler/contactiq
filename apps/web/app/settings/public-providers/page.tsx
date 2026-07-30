"use client";

import { FormEvent, useCallback, useEffect, useState } from "react";

import { API_URL } from "../../contacts/constants";

type Provider = {
  domain: string;
  created_at: string | null;
};

type ProviderResponse = {
  items: Provider[];
  total: number;
  public_email_contacts: number;
  cache: {
    domains_cached: number;
    cache_age_seconds: number;
    cache_ttl_seconds: number;
  };
};

export default function PublicProvidersPage() {
  const [items, setItems] = useState<Provider[]>([]);
  const [domain, setDomain] = useState("");
  const [search, setSearch] = useState("");
  const [stats, setStats] = useState<ProviderResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [message, setMessage] = useState<string | null>(null);

  const loadProviders = useCallback(async () => {
    try {
      setLoading(true);

      const params = new URLSearchParams();
      if (search.trim()) params.set("search", search.trim());

      const response = await fetch(
        `${API_URL}/admin/public-providers?${params.toString()}`,
        { cache: "no-store" },
      );

      if (!response.ok) {
        throw new Error("Seznama ni bilo mogoče naložiti.");
      }

      const data: ProviderResponse = await response.json();
      setItems(data.items);
      setStats(data);
    } catch (error) {
      setMessage(
        error instanceof Error
          ? error.message
          : "Prišlo je do napake.",
      );
    } finally {
      setLoading(false);
    }
  }, [search]);

  useEffect(() => {
    void loadProviders();
  }, [loadProviders]);

  async function addProvider(event: FormEvent) {
    event.preventDefault();
    setMessage(null);

    const response = await fetch(
      `${API_URL}/admin/public-providers`,
      {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ domain }),
      },
    );

    if (!response.ok) {
      const body = await response.json().catch(() => null);
      setMessage(body?.detail ?? "Domene ni bilo mogoče dodati.");
      return;
    }

    setDomain("");
    setMessage("Domena je dodana in cache osvežen.");
    await loadProviders();
  }

  async function deleteProvider(value: string) {
    const response = await fetch(
      `${API_URL}/admin/public-providers/${encodeURIComponent(value)}`,
      { method: "DELETE" },
    );

    if (!response.ok) {
      setMessage("Domene ni bilo mogoče odstraniti.");
      return;
    }

    setMessage("Domena je odstranjena iz baze.");
    await loadProviders();
  }

  async function reloadCache() {
    const response = await fetch(
      `${API_URL}/admin/public-providers/reload-cache`,
      { method: "POST" },
    );

    if (!response.ok) {
      setMessage("Cache-a ni bilo mogoče osvežiti.");
      return;
    }

    setMessage("Cache je osvežen.");
    await loadProviders();
  }

  return (
    <>
      <header className="pageHeader">
        <div>
          <p className="eyebrow">UPRAVLJANJE</p>
          <h1>Public Providers</h1>
          <p className="muted">
            Domene javnih e-poštnih ponudnikov, ki jih worker ne sme pregledovati.
          </p>
        </div>

        <button
          type="button"
          className="secondaryButton"
          onClick={() => void reloadCache()}
        >
          Osveži cache
        </button>
      </header>

      {message && (
        <div className="alert" style={{ marginBottom: 20 }}>
          <p>{message}</p>
        </div>
      )}

      <section className="panel pagePanel">
        <div className="panelTop contactsPanelTop">
          <div>
            <h2>Register domen</h2>
            <p className="muted">
              {stats?.total ?? 0} domen · {stats?.public_email_contacts ?? 0} kontaktov
              s statusom PUBLIC_EMAIL · {stats?.cache.domains_cached ?? 0} domen v cache-u
            </p>
          </div>

          <form className="filters" onSubmit={addProvider}>
            <input
              value={domain}
              onChange={(event) => setDomain(event.target.value)}
              placeholder="npr. mailbox.org"
              required
            />
            <button type="submit">Dodaj domeno</button>
          </form>
        </div>

        <div className="filters" style={{ marginBottom: 18 }}>
          <input
            type="search"
            value={search}
            onChange={(event) => setSearch(event.target.value)}
            placeholder="Išči domeno"
          />
        </div>

        {loading ? (
          <div className="stateMessage largeState">
            <div className="spinner" />
            <p>Nalaganje domen …</p>
          </div>
        ) : (
          <div className="tableWrapper">
            <table>
              <thead>
                <tr>
                  <th>Domena</th>
                  <th>Dodana</th>
                  <th>Akcija</th>
                </tr>
              </thead>
              <tbody>
                {items.map((item) => (
                  <tr key={item.domain}>
                    <td><strong>{item.domain}</strong></td>
                    <td>
                      {item.created_at
                        ? new Intl.DateTimeFormat("sl-SI", {
                            dateStyle: "medium",
                            timeStyle: "short",
                          }).format(new Date(item.created_at))
                        : "—"}
                    </td>
                    <td>
                      <button
                        type="button"
                        className="ghostButton"
                        onClick={() => void deleteProvider(item.domain)}
                      >
                        Odstrani
                      </button>
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
