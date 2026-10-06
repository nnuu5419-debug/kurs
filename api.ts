const API = process.env.NEXT_PUBLIC_API!;

export async function api<T = any>(path: string, opts: RequestInit = {}): Promise<T> {
  const res = await fetch(API + path, {
    credentials: "include", cache: "no-store",
    headers: { "Content-Type": "application/json" }, ...opts,
  });
  if (!res.ok) throw Object.assign(new Error(res.statusText), { status: res.status });
  return res.json();
}
export const money = (cents: number, cur = "usd") =>
  cents === 0 ? "Free" : new Intl.NumberFormat("en", { style: "currency", currency: cur }).format(cents / 100);
