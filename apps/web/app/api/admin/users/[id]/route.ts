import { NextRequest, NextResponse } from "next/server";
import { createClient } from "@supabase/supabase-js";

export const dynamic = "force-dynamic";

function adminClient() {
  const url = process.env.NEXT_PUBLIC_SUPABASE_URL;
  const serviceRoleKey = process.env.SUPABASE_SERVICE_ROLE_KEY;
  if (!url || !serviceRoleKey) throw new Error("Supabase server variables are missing.");
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

  const role = data.user.app_metadata?.role ?? data.user.user_metadata?.role;
  if (role === "admin") return data.user;

  const { data: profile } = await supabase
    .from("profiles")
    .select("role")
    .eq("id", data.user.id)
    .maybeSingle();
  if (profile?.role === "admin") return data.user;

  const emails = (process.env.CONTACTIQ_ADMIN_EMAILS ?? "")
    .split(",")
    .map((value) => value.trim().toLowerCase())
    .filter(Boolean);
  return data.user.email && emails.includes(data.user.email.toLowerCase())
    ? data.user
    : null;
}

export async function PATCH(
  request: NextRequest,
  context: { params: Promise<{ id: string }> },
) {
  try {
    const actor = await requireAdmin(request);
    if (!actor) {
      return NextResponse.json({ detail: "Administrator access required." }, { status: 403 });
    }

    const { id } = await context.params;
    const body = (await request.json()) as {
      role?: "admin" | "user";
      active?: boolean;
    };

    if (actor.id === id && body.active === false) {
      return NextResponse.json(
        { detail: "You cannot deactivate your own account." },
        { status: 400 },
      );
    }

    const supabase = adminClient();
    const { data: current, error: readError } = await supabase.auth.admin.getUserById(id);
    if (readError) throw readError;

    const role = body.role === "admin" ? "admin" : body.role === "user" ? "user" : undefined;
    const { error } = await supabase.auth.admin.updateUserById(id, {
      ...(role
        ? {
            app_metadata: { ...current.user.app_metadata, role },
            user_metadata: { ...current.user.user_metadata, role },
          }
        : {}),
      ...(typeof body.active === "boolean"
        ? { ban_duration: body.active ? "none" : "876000h" }
        : {}),
    });
    if (error) throw error;

    const profileUpdates: Record<string, unknown> = {};
    if (role) profileUpdates.role = role;
    if (typeof body.active === "boolean") profileUpdates.active = body.active;
    if (Object.keys(profileUpdates).length) {
      await supabase.from("profiles").update(profileUpdates).eq("id", id);
    }

    return NextResponse.json({ ok: true });
  } catch (error) {
    return NextResponse.json(
      { detail: error instanceof Error ? error.message : "Unable to update user." },
      { status: 500 },
    );
  }
}
