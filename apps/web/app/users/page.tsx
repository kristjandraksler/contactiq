"use client";

import { FormEvent, useCallback, useEffect, useState } from "react";

import { useAuth } from "@/components/auth/AuthProvider";
import { createClient } from "@/lib/supabase/client";

import "./users.css";

const API_URL =
  process.env.NEXT_PUBLIC_API_URL ??
  "http://127.0.0.1:8000";

type ManagedUser = {
  id: string;
  email: string;
  full_name: string | null;
  role: "admin" | "user";
  active: boolean;
  created_at: string | null;
  last_sign_in_at: string | null;
};

async function bearerToken() {
  const supabase = createClient();
  const {
    data: { session },
  } = await supabase.auth.getSession();

  return session?.access_token ?? null;
}

export default function UsersPage() {
  const { profile, loading: authLoading } = useAuth();
  const [items, setItems] = useState<ManagedUser[]>([]);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [fullName, setFullName] = useState("");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [role, setRole] = useState<"admin" | "user">("user");

  const load = useCallback(async () => {
    try {
      setLoading(true);
      setError(null);

      const token = await bearerToken();

      const response = await fetch(`${API_URL}/admin/users`, {
        cache: "no-store",
        headers: {
          Authorization: `Bearer ${token ?? ""}`,
        },
      });

      const data = await response.json();

      if (!response.ok) {
        throw new Error(data.detail ?? "Uporabnikov ni bilo mogoče naložiti.");
      }

      setItems(data.items ?? []);
    } catch (err) {
      setError(
        err instanceof Error ? err.message : "Nepričakovana napaka.",
      );
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    if (profile?.role === "admin") {
      void load();
    } else if (!authLoading) {
      setLoading(false);
    }
  }, [authLoading, load, profile?.role]);

  async function createUser(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();

    try {
      setSaving(true);
      setError(null);

      const token = await bearerToken();
      const response = await fetch(`${API_URL}/admin/users`, {
        method: "POST",
        headers: {
          Authorization: `Bearer ${token ?? ""}`,
          "Content-Type": "application/json",
        },
        body: JSON.stringify({
          email: email.trim(),
          password,
          full_name: fullName.trim() || null,
          role,
        }),
      });

      const data = await response.json();

      if (!response.ok) {
        throw new Error(data.detail ?? "Uporabnika ni bilo mogoče ustvariti.");
      }

      setFullName("");
      setEmail("");
      setPassword("");
      setRole("user");
      await load();
    } catch (err) {
      setError(
        err instanceof Error ? err.message : "Nepričakovana napaka.",
      );
    } finally {
      setSaving(false);
    }
  }

  async function updateUser(
    userId: string,
    updates: { role?: "admin" | "user"; active?: boolean },
  ) {
    try {
      setError(null);
      const token = await bearerToken();

      const response = await fetch(
        `${API_URL}/admin/users/${userId}`,
        {
          method: "PATCH",
          headers: {
            Authorization: `Bearer ${token ?? ""}`,
            "Content-Type": "application/json",
          },
          body: JSON.stringify(updates),
        },
      );

      const data = await response.json();

      if (!response.ok) {
        throw new Error(data.detail ?? "Uporabnika ni bilo mogoče posodobiti.");
      }

      await load();
    } catch (err) {
      setError(
        err instanceof Error ? err.message : "Nepričakovana napaka.",
      );
    }
  }

  if (!authLoading && profile?.role !== "admin") {
    return (
      <div className="usersPage">
        <div className="usersAccessDenied">
          <h1>Dostop ni dovoljen</h1>
          <p>To stran lahko odpre samo administrator.</p>
        </div>
      </div>
    );
  }

  return (
    <div className="usersPage">
      <header className="usersHeader">
        <div>
          <p>USER MANAGEMENT</p>
          <h1>Uporabniki</h1>
          <span>
            Ustvari uporabnike in upravljaj njihove vloge ter dostop.
          </span>
        </div>
      </header>

      <section className="usersGrid">
        <form className="userCreateCard" onSubmit={createUser}>
          <div>
            <p>NOV UPORABNIK</p>
            <h2>Dodaj dostop</h2>
          </div>

          <label>
            <span>Ime</span>
            <input
              value={fullName}
              onChange={(event) => setFullName(event.target.value)}
              placeholder="Ime in priimek"
            />
          </label>

          <label>
            <span>Email</span>
            <input
              type="email"
              required
              value={email}
              onChange={(event) => setEmail(event.target.value)}
              placeholder="name@company.com"
            />
          </label>

          <label>
            <span>Začasno geslo</span>
            <input
              type="password"
              required
              minLength={8}
              value={password}
              onChange={(event) => setPassword(event.target.value)}
              placeholder="Najmanj 8 znakov"
            />
          </label>

          <label>
            <span>Vloga</span>
            <select
              value={role}
              onChange={(event) =>
                setRole(event.target.value as "admin" | "user")
              }
            >
              <option value="user">User</option>
              <option value="admin">Admin</option>
            </select>
          </label>

          <button type="submit" disabled={saving}>
            {saving ? "Ustvarjam …" : "Ustvari uporabnika"}
          </button>
        </form>

        <section className="usersPanel">
          <div className="usersPanelHead">
            <div>
              <p>WORKSPACE ACCESS</p>
              <h2>Aktivni uporabniki</h2>
            </div>
            <strong>{items.length}</strong>
          </div>

          {error && <div className="usersError">{error}</div>}

          {loading ? (
            <div className="usersEmpty">Nalaganje uporabnikov …</div>
          ) : (
            <div className="usersTableWrap">
              <table>
                <thead>
                  <tr>
                    <th>Uporabnik</th>
                    <th>Vloga</th>
                    <th>Status</th>
                    <th>Zadnja prijava</th>
                    <th />
                  </tr>
                </thead>
                <tbody>
                  {items.map((item) => (
                    <tr key={item.id}>
                      <td>
                        <strong>{item.full_name || item.email}</strong>
                        <small>{item.email}</small>
                      </td>
                      <td>
                        <select
                          value={item.role}
                          onChange={(event) =>
                            void updateUser(item.id, {
                              role: event.target.value as "admin" | "user",
                            })
                          }
                        >
                          <option value="user">User</option>
                          <option value="admin">Admin</option>
                        </select>
                      </td>
                      <td>
                        <span className={item.active ? "active" : "inactive"}>
                          {item.active ? "Active" : "Disabled"}
                        </span>
                      </td>
                      <td>
                        {item.last_sign_in_at
                          ? new Intl.DateTimeFormat("sl-SI", {
                              dateStyle: "medium",
                              timeStyle: "short",
                            }).format(new Date(item.last_sign_in_at))
                          : "—"}
                      </td>
                      <td>
                        <button
                          type="button"
                          className="userToggle"
                          onClick={() =>
                            void updateUser(item.id, {
                              active: !item.active,
                            })
                          }
                        >
                          {item.active ? "Deaktiviraj" : "Aktiviraj"}
                        </button>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </section>
      </section>
    </div>
  );
}
