"use client";

import { FormEvent, useCallback, useEffect, useState } from "react";
import "./identity.css";

const API_URL = process.env.NEXT_PUBLIC_API_URL ?? "http://127.0.0.1:8000";

type IdentityResult = {
  id: string;
  email: string;
  status: "PENDING" | "PROCESSING" | "VERIFIED" | "NEEDS_REVIEW" | "NOT_FOUND" | "FAILED";
  person_name: string | null;
  company_name: string | null;
  company_domain: string | null;
  phone: string | null;
  phone_type: string | null;
  confidence: number;
  source_url: string | null;
  evidence: string[];
  updated_at: string;
};

export default function IdentityPage() {
  const [email, setEmail] = useState("");
  const [items, setItems] = useState<IdentityResult[]>([]);
  const [loading, setLoading] = useState(true);
  const [submitting, setSubmitting] = useState(false);
  const [message, setMessage] = useState<string | null>(null);

  const load = useCallback(async () => {
    try {
      setLoading(true);
      const response = await fetch(`${API_URL}/identity/results?limit=100`, { cache: "no-store" });
      const payload = await response.json();
      if (!response.ok) throw new Error(payload.detail ?? "Identity results could not be loaded.");
      setItems(payload.items ?? []);
    } catch (error) {
      setMessage(error instanceof Error ? error.message : "Unexpected error.");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => { void load(); }, [load]);

  async function resolveEmail(event: FormEvent) {
    event.preventDefault();
    try {
      setSubmitting(true);
      setMessage(null);
      const response = await fetch(`${API_URL}/identity/resolve`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ email: email.trim() }),
      });
      const payload = await response.json();
      if (!response.ok) throw new Error(payload.detail ?? "Identity search failed.");
      setEmail("");
      setMessage("Identity search completed.");
      await load();
    } catch (error) {
      setMessage(error instanceof Error ? error.message : "Identity search failed.");
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <div className="identityPage">
      <header className="identityHeader">
        <div>
          <p className="eyebrow">IDENTITY RESOLVER</p>
          <h1>Public email enrichment</h1>
          <p className="muted">Resolve Gmail and other public email addresses separately from the standard company-domain worker.</p>
        </div>
        <form className="identitySearch" onSubmit={resolveEmail}>
          <input type="email" value={email} onChange={(event) => setEmail(event.target.value)} placeholder="name@gmail.com" required />
          <button type="submit" disabled={submitting}>{submitting ? "Searching…" : "Resolve identity"}</button>
        </form>
      </header>

      {message && <div className="identityAlert">{message}</div>}

      <section className="identityPanel">
        <div className="identityPanelTop">
          <div><h2>Identity results</h2><p className="muted">Only publicly available business contact evidence is stored.</p></div>
          <button type="button" className="secondaryButton" onClick={() => void load()}>Refresh</button>
        </div>

        {loading ? <div className="identityState">Loading…</div> : (
          <div className="identityTableWrap">
            <table>
              <thead><tr><th>Email</th><th>Identity</th><th>Company</th><th>Phone</th><th>Confidence</th><th>Status</th><th>Source</th></tr></thead>
              <tbody>
                {items.map((item) => (
                  <tr key={item.id}>
                    <td><strong>{item.email}</strong></td>
                    <td>{item.person_name ?? "—"}</td>
                    <td>{item.company_name ?? item.company_domain ?? "—"}</td>
                    <td>{item.phone ? <><strong>{item.phone}</strong><small>{item.phone_type ?? "unknown"}</small></> : "—"}</td>
                    <td><span className={`confidence confidence${Math.floor(item.confidence / 20)}`}>{item.confidence}%</span></td>
                    <td><span className={`identityStatus status${item.status}`}>{item.status.replaceAll("_", " ")}</span></td>
                    <td>{item.source_url ? <a href={item.source_url} target="_blank" rel="noreferrer">Open source</a> : "—"}</td>
                  </tr>
                ))}
                {!items.length && <tr><td colSpan={7} className="identityEmpty">No identity searches yet.</td></tr>}
              </tbody>
            </table>
          </div>
        )}
      </section>
    </div>
  );
}
