"use client";

import type { User } from "@supabase/supabase-js";
import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useState,
} from "react";

import { createClient } from "@/lib/supabase/client";

export type AppRole = "admin" | "user";

export type Profile = {
  id: string;
  email: string;
  full_name: string | null;
  role: AppRole;
  active: boolean;
};

type AuthContextValue = {
  user: User | null;
  profile: Profile | null;
  loading: boolean;
  refreshProfile: () => Promise<void>;
  signOut: () => Promise<void>;
};

const AuthContext = createContext<AuthContextValue | null>(null);

export default function AuthProvider({
  children,
}: {
  children: React.ReactNode;
}) {
  const supabase = useMemo(() => createClient(), []);
  const [user, setUser] = useState<User | null>(null);
  const [profile, setProfile] = useState<Profile | null>(null);
  const [loading, setLoading] = useState(true);

  const loadProfile = useCallback(
    async (currentUser: User | null) => {
      setUser(currentUser);

      if (!currentUser) {
        setProfile(null);
        setLoading(false);
        return;
      }

      const { data } = await supabase
        .from("profiles")
        .select("id,email,full_name,role,active")
        .eq("id", currentUser.id)
        .maybeSingle();

      setProfile((data as Profile | null) ?? null);
      setLoading(false);
    },
    [supabase],
  );

  const refreshProfile = useCallback(async () => {
    const {
      data: { user: currentUser },
    } = await supabase.auth.getUser();

    await loadProfile(currentUser);
  }, [loadProfile, supabase]);

  useEffect(() => {
    void refreshProfile();

    const {
      data: { subscription },
    } = supabase.auth.onAuthStateChange((_event, session) => {
      void loadProfile(session?.user ?? null);
    });

    return () => subscription.unsubscribe();
  }, [loadProfile, refreshProfile, supabase]);

  async function signOut() {
    await supabase.auth.signOut();
    window.location.href = "/login";
  }

  return (
    <AuthContext.Provider
      value={{
        user,
        profile,
        loading,
        refreshProfile,
        signOut,
      }}
    >
      {children}
    </AuthContext.Provider>
  );
}

export function useAuth() {
  const context = useContext(AuthContext);

  if (!context) {
    throw new Error("useAuth must be used inside AuthProvider.");
  }

  return context;
}
