"use client";
import { useState } from "react";
import { api } from "@/lib/api";

type Turn = { role: "user" | "assistant"; content: string; corrections?: { original: string; fixed: string; why: string }[] };

export default function Tutor() {
  const [turns, setTurns] = useState<Turn[]>([{ role: "assistant", content: "Hi! I'm your English tutor. What did you do today?" }]);
  const [text, setText] = useState("");
  const [busy, setBusy] = useState(false);

  const send = async () => {
    if (!text.trim() || busy) return;
    const next: Turn[] = [...turns, { role: "user", content: text }];
    setTurns(next); setText(""); setBusy(true);
    try {
      const r = await api("/ai/tutor", { method: "POST", body: JSON.stringify({ messages: next.map(({ role, content }) => ({ role, content })) }) });
      setTurns([...next, { role: "assistant", content: r.reply, corrections: r.corrections }]);
    } finally { setBusy(false); }
  };
  return (
    <div className="max-w-2xl space-y-3">
      <h1 className="text-2xl font-bold">AI tutor</h1>
      {turns.map((t, i) => (
        <div key={i} className={`rounded-lg p-3 ${t.role === "user" ? "bg-ink text-white ml-12" : "bg-white mr-12"}`}>
          {t.content}
          {t.corrections?.map((c, j) => (
            <p key={j} className="mt-2 text-sm border-l-4 border-sun pl-2"><s>{c.original}</s> → <b>{c.fixed}</b><br />{c.why}</p>
          ))}
        </div>
      ))}
      <div className="flex gap-2">
        <input value={text} onChange={(e) => setText(e.target.value)} onKeyDown={(e) => e.key === "Enter" && send()}
               placeholder="Write in English…" className="flex-1 border rounded-lg px-3 py-2" />
        <button onClick={send} disabled={busy} className="btn bg-ink text-white">{busy ? "…" : "Send"}</button>
      </div>
    </div>
  );
}
