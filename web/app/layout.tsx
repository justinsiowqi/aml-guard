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
      <body className="flex h-screen overflow-hidden bg-background font-sans text-on-surface antialiased">
        <Rail />
        <main className="flex h-full flex-1 flex-col overflow-hidden bg-background">{children}</main>
      </body>
    </html>
  );
}
