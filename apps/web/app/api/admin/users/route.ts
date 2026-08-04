import { NextRequest, NextResponse } from "next/server";
import { createClient } from "@supabase/supabase-js";

export const dynamic = "force-dynamic";

function adminClient() {
  const url = process.env.NEXT_PUBLIC_SUPABASE_URL;
  const serviceRoleKey = process.env.SUPABASE_SERVICE_ROLE_KEY;

  if (!url || !serviceRoleKey) {
    throw new Error(
      "Missing NEXT_PUBLIC_SUPABASE_URL or SUPABASE_SERVICE_ROLE_KEY.",
    );
  }

  return createClient(url, serviceRoleKey, {
    auth: { autoRefreshToken: false, persistSession: false },
  });
}

async function requireAdmin(request: NextRequest) {
  const token = request.headers.get("authorization")?.replace(/^Bearer\s+/i, "");
  if (!token) return null;

  const supabase = adminClient();
  const { data, error } = await supabase.auth.getUser(token);
  if (error || !data.user) return null;

  const metadataRole =
    data.user.app_metadata?.role ?? data.user.user_metadata?.role;

  if (metadataRole === "admin") return data.user;

  // Compatibility with projects that keep roles in a public.profiles table.
  const { data: profile } = await supabase
    .from("profiles")
    .select("role")
    .eq("id", data.user.id)
    .maybeSingle();

  if (profile?.role === "admin") return data.user;

  const adminEmails = (process.env.CONTACTIQ_ADMIN_EMAILS ?? "")
    .split(",")
    .map((email) => email.trim().toLowerCase())
    .filter(Boolean);

  return data.user.email && adminEmails.includes(data.user.email.toLowerCase())
    ? data.user
    : null;
}

function serializeUser(user: {
  id: string;
  email?: string;
  created_at: string;
  last_sign_in_at?: string;
  banned_until?: string;
  app_metadata?: Record<string, unknown>;
  user_metadata?: Record<string, unknown>;
}) {
  const bannedUntil = user.banned_until
    ? new Date(user.banned_until).getTime()
    : 0;

  return {
    id: user.id,
    email: user.email ?? "",
    full_name:
      (user.user_metadata?.full_name as string | undefined) ??
      (user.user_metadata?.name as string | undefined) ??
      null,
    role:
      user.app_metadata?.role === "admin" || user.user_metadata?.role === "admin"
        ? "admin"
        : "user",
    active: !bannedUntil || bannedUntil <= Date.now(),
    created_at: user.created_at ?? null,
    last_sign_in_at: user.last_sign_in_at ?? null,
  };
}

export async function GET(request: NextRequest) {
  try {
    if (!(await requireAdmin(request))) {
      return NextResponse.json({ detail: "Administrator access required." }, { status: 403 });
    }

    const supabase = adminClient();
    const users = [];
    let page = 1;

    while (true) {
      const { data, error } = await supabase.auth.admin.listUsers({
        page,
        perPage: 1000,
      });

      if (error) throw error;
      users.push(...data.users);
      if (data.users.length < 1000) break;
      page += 1;
    }

    return NextResponse.json({
      items: users
        .map(serializeUser)
        .sort((a, b) => a.email.localeCompare(b.email)),
    });
  } catch (error) {
    return NextResponse.json(
      { detail: error instanceof Error ? error.message : "Unable to load users." },
      { status: 500 },
    );
  }
}

export async function POST(request: NextRequest) {
  try {
    if (!(await requireAdmin(request))) {
      return NextResponse.json({ detail: "Administrator access required." }, { status: 403 });
    }

    const body = (await request.json()) as {
      email?: string;
      password?: string;
      full_name?: string | null;
      role?: "admin" | "user";
    };

    const email = body.email?.trim().toLowerCase();
    const password = body.password ?? "";
    const role = body.role === "admin" ? "admin" : "user";

    if (!email) {
      return NextResponse.json({ detail: "Email is required." }, { status: 400 });
    }
    if (password.length < 8) {
      return NextResponse.json(
        { detail: "Password must contain at least 8 characters." },
        { status: 400 },
      );
    }

    const supabase = adminClient();
    const { data, error } = await supabase.auth.admin.createUser({
      email,
      password,
      email_confirm: true,
      app_metadata: { role },
      user_metadata: {
        full_name: body.full_name?.trim() || null,
        role,
      },
    });

    if (error) throw error;

    // Keep an existing profiles table in sync when the project uses one.
    await supabase.from("profiles").upsert(
      {
        id: data.user.id,
        email,
        full_name: body.full_name?.trim() || null,
        role,
        active: true,
      },
      { onConflict: "id" },
    );

    return NextResponse.json({ item: serializeUser(data.user) }, { status: 201 });
  } catch (error) {
    return NextResponse.json(
      { detail: error instanceof Error ? error.message : "Unable to create user." },
      { status: 500 },
    );
  }
}
