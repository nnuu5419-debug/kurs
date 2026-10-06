"use client";
import { createContext, useContext, useEffect, useRef, useState } from "react";
import { api } from "@/lib/api";

type User = { id: number; email: string; name: string; picture: string; is_admin: boolean; level_estimate: string | null };
const Ctx = createContext<{ user: User | null; loading: boolean; logout: () => void }>({ user: null, loading: true, logout() {} });
export const useUser = () => useContext(Ctx);

export function AuthProvider({ children }: { children: React.ReactNode }) {
  const [user, setUser] = useState<User | null>(null);
  const [loading, setLoading] = useState(true);
  useEffect(() => { api("/auth/me").then(setUser).catch(() => setUser(null)).finally(() => setLoading(false)); }, []);
  const logout = async () => { await api("/auth/logout", { method: "POST" }); setUser(null); };
  if (loading) return <p className="p-10">Loading…</p>;
  if (!user) return <Login onDone={setUser} />;
  return <Ctx.Provider value={{ user, loading, logout }}>{children}</Ctx.Provider>;
}

function Login({ onDone }: { onDone: (u: User) => void }) {
  const box = useRef<HTMLDivElement>(null);
  useEffect(() => {
    const s = document.createElement("script");
    s.src = "https://accounts.google.com/gsi/client"; s.async = true;
    s.onload = () => {
      const g = (window as any).google.accounts.id;
      g.initialize({
        client_id: process.env.NEXT_PUBLIC_GOOGLE_CLIENT_ID,
        callback: async (r: { credential: string }) =>
          onDone(await api("/auth/google", { method: "POST", body: JSON.stringify({ credential: r.credential }) })),
      });
      g.renderButton(box.current, { theme: "filled_blue", size: "large", text: "continue_with" });
    };
    document.body.appendChild(s);
  }, [onDone]);
  return (
    <main className="min-h-screen grid place-items-center bg-ink text-white p-6">
      <div className="max-w-md text-center space-y-6">
        <h1 className="text-4xl font-bold">Speak English with confidence</h1>
        <p className="text-white/80">Sign in with Google to start the free Beginner level and take the placement test.</p>
        <div ref={box} className="flex justify-center" />
      </div>
    </main>
  );
}
