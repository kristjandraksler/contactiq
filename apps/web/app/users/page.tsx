"use client";

import { FormEvent, useCallback, useEffect, useState } from "react";

import { useAuth } from "@/components/auth/AuthProvider";
import { createClient } from "@/lib/supabase/client";

import "./users.css";

const USERS_API = "/api/admin/users";

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

      const response = await fetch(USERS_API, {
        cache: "no-store",
        headers: {
          Authorization: `Bearer ${token ?? ""}`,
        },
      });

      const data = await response.json().catch(() => ({}));

      if (!response.ok) {
        throw new Error(data.detail ?? "Users could not be loaded.");
      }

      setItems(data.items ?? []);
    } catch (err) {
      setError(
        err instanceof Error ? err.message : "Unexpected error.",
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
      const response = await fetch(USERS_API, {
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

      const data = await response.json().catch(() => ({}));

      if (!response.ok) {
        throw new Error(data.detail ?? "The user could not be created.");
      }

      setFullName("");
      setEmail("");
      setPassword("");
      setRole("user");
      await load();
    } catch (err) {
      setError(
        err instanceof Error ? err.message : "Unexpected error.",
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
        `${USERS_API}/${userId}`,
        {
          method: "PATCH",
          headers: {
            Authorization: `Bearer ${token ?? ""}`,
            "Content-Type": "application/json",
          },
          body: JSON.stringify(updates),
        },
      );

      const data = await response.json().catch(() => ({}));

      if (!response.ok) {
        throw new Error(data.detail ?? "The user could not be updated.");
      }

      await load();
    } catch (err) {
      setError(
        err instanceof Error ? err.message : "Unexpected error.",
      );
    }
  }

  if (!authLoading && profile?.role !== "admin") {
    return (
      <div className="usersPage">
        <div className="usersAccessDenied">
          <h1>Access denied</h1>
          <p>Only administrators can open this page.</p>
        </div>
      </div>
    );
  }

  return (
    <div className="usersPage">
      <header className="usersHeader">
        <div>
          <p>USER MANAGEMENT</p>
          <h1>Users</h1>
          <span>
            Create users and manage their roles and access.
          </span>
        </div>
      </header>

      <section className="usersGrid">
        <form className="userCreateCard" onSubmit={createUser}>
          <div>
            <p>NEW USER</p>
            <h2>Add access</h2>
          </div>

          <label>
            <span>Name</span>
            <input
              value={fullName}
              onChange={(event) => setFullName(event.target.value)}
              placeholder="Full name"
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
            <span>Temporary password</span>
            <input
              type="password"
              required
              minLength={8}
              value={password}
              onChange={(event) => setPassword(event.target.value)}
              placeholder="At least 8 characters"
            />
          </label>

          <label>
            <span>Role</span>
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
            {saving ? "Creating…" : "Create user"}
          </button>
        </form>

        <section className="usersPanel">
          <div className="usersPanelHead">
            <div>
              <p>WORKSPACE ACCESS</p>
              <h2>Workspace users</h2>
            </div>
            <strong>{items.length}</strong>
          </div>

          {error && <div className="usersError">{error}</div>}

          {loading ? (
            <div className="usersEmpty">Loading users…</div>
          ) : (
            <div className="usersTableWrap">
              <table>
                <thead>
                  <tr>
                    <th>User</th>
                    <th>Role</th>
                    <th>Status</th>
                    <th>Last sign-in</th>
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
                          ? new Intl.DateTimeFormat("en-GB", {
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
                          {item.active ? "Deactivate" : "Activate"}
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
