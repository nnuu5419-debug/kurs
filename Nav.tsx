"use client";
import Link from "next/link";
import { useUser } from "./Auth";

export default function Nav() {
  const { user, logout } = useUser();
  return (
    <header className="bg-ink text-white">
      <nav className="mx-auto max-w-5xl flex flex-wrap items-center gap-5 p-4">
        <Link href="/" className="text-xl font-bold mr-auto">Lingua</Link>
        <Link href="/placement">Level test</Link>
        <Link href="/tutor">AI tutor</Link>
        <Link href="/speaking">Speaking</Link>
        {user?.is_admin && <Link href="/admin" className="text-sun">Admin</Link>}
        <button onClick={logout} className="underline">Sign out</button>
      </nav>
    </header>
  );
}
