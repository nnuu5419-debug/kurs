import "./globals.css";
import { AuthProvider } from "@/components/Auth";
import Nav from "@/components/Nav";

export const metadata = { title: "Lingua – learn English" };
export default function Root({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en"><body>
      <AuthProvider><Nav /><div className="mx-auto max-w-5xl p-4 md:p-8">{children}</div></AuthProvider>
    </body></html>
  );
}
