"use client";

import { FormEvent, useState } from "react";


import { createClient } from "@/lib/supabase/client";

import "./login.css";

export default function LoginPage() {
  
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [showPassword, setShowPassword] = useState(false);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();

    try {
      setLoading(true);
      setError(null);

      const supabase = createClient();
      const { error: loginError } =
        await supabase.auth.signInWithPassword({
          email: email.trim(),
          password,
        });

      if (loginError) {
        throw loginError;
      }

      window.location.href = "/";
    } catch (err) {
      setError(
        err instanceof Error
          ? err.message
          : "Prijava ni uspela.",
      );
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="loginPage">
      <section className="loginBrandPanel">
        <div className="loginBrand">
          <span>CI</span>
          <strong>
            Contact<i>IQ</i>
          </strong>
        </div>

        <div className="loginHeroCopy">
          <p>INTERNAL PLATFORM</p>
          <h1>Contact intelligence for focused outreach.</h1>
          <span>
            Discover verified phone numbers, organize companies
            and keep every call summary in one workspace.
          </span>
        </div>

        <div className="loginFeatureGrid">
          <article>
            <strong>Phone Discovery</strong>
            <span>Research and verify business contact numbers.</span>
          </article>
          <article>
            <strong>Company Intelligence</strong>
            <span>Understand domains, countries and success rates.</span>
          </article>
          <article>
            <strong>Call Intelligence</strong>
            <span>Track conversations, outcomes and follow-ups.</span>
          </article>
        </div>

        <small>ContactIQ · Secure internal workspace</small>
      </section>

      <section className="loginFormPanel">
        <form className="loginCard" onSubmit={submit}>
          <div className="loginCardHeader">
            <span>SECURE ACCESS</span>
            <h2>Welcome back</h2>
            <p>Sign in with your ContactIQ account.</p>
          </div>

          <label>
            <span>Email</span>
            <input
              type="email"
              autoComplete="email"
              required
              value={email}
              onChange={(event) => setEmail(event.target.value)}
              placeholder="name@company.com"
            />
          </label>

          <label>
            <span>Password</span>
            <div className="passwordField">
              <input
                type={showPassword ? "text" : "password"}
                autoComplete="current-password"
                required
                value={password}
                onChange={(event) =>
                  setPassword(event.target.value)
                }
                placeholder="Enter your password"
              />
              <button
                type="button"
                onClick={() => setShowPassword((value) => !value)}
              >
                {showPassword ? "Hide" : "Show"}
              </button>
            </div>
          </label>

          {error && <div className="loginError">{error}</div>}

          <button
            className="loginSubmit"
            type="submit"
            disabled={loading}
          >
            {loading ? "Signing in …" : "Sign in"}
          </button>

          <div className="loginEnvironment">
            <span>
              <i />
              Production
            </span>
            <small>Supabase Auth</small>
          </div>
        </form>
      </section>
    </div>
  );
}
