import type { Metadata } from "next";
import "./globals.css";
import Rail from "@/components/Rail";

export const metadata: Metadata = {
  title: "AML Guard — Investigate",
  description: "Agentic financial-crime investigation with cited evidence.",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en">
      <body className="min-h-screen bg-base text-text font-body antialiased">
        <div className="flex min-h-screen">
          <Rail />
          <main className="flex-1 overflow-x-hidden">{children}</main>
        </div>
      </body>
    </html>
  );
}
