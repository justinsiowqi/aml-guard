"use client";

import { Landmark, Search, AlertTriangle, Network, Archive, Plus } from "lucide-react";

type NavItem = {
  icon: typeof Landmark;
  label: string;
  active?: boolean;
};

const items: NavItem[] = [
  { icon: Landmark, label: "Ledger" },
  { icon: Search, label: "Investigations", active: true },
  { icon: AlertTriangle, label: "Anomalies" },
  { icon: Network, label: "Nodes" },
  { icon: Archive, label: "Archive" },
];

export default function Rail() {
  return (
    <nav className="flex h-full w-64 shrink-0 flex-col space-y-2 border-r border-outline-variant/10 bg-surface-container-low px-4 py-8">
      <div className="mb-8 px-2">
        <h1 className="text-xl font-bold text-primary">Case Management</h1>
        <p className="mt-1 text-sm tracking-wide text-on-surface-variant">Active Protocol: 704</p>
      </div>

      <button
        type="button"
        className="mb-6 flex w-full items-center justify-center gap-2 rounded bg-gradient-to-br from-primary to-primary-container px-4 py-2 font-medium text-white transition-opacity hover:opacity-90"
      >
        <Plus size={18} strokeWidth={2} />
        New Investigation
      </button>

      <div className="flex-1 space-y-1">
        {items.map(({ icon: Icon, label, active }) => (
          <a
            key={label}
            href="#"
            className={
              active
                ? "flex items-center gap-3 rounded bg-surface-container-lowest px-3 py-2 text-sm font-semibold tracking-wide text-primary-container shadow-sm transition-all duration-200 hover:translate-x-1 active:opacity-80"
                : "flex items-center gap-3 px-3 py-2 text-sm tracking-wide text-on-surface-variant transition-all duration-200 hover:translate-x-1 hover:bg-surface-container"
            }
          >
            <Icon size={20} strokeWidth={active ? 2.25 : 1.75} />
            <span>{label}</span>
          </a>
        ))}
      </div>

      <div className="mt-auto border-t border-outline-variant/20 px-2 pt-4">
        <div className="flex items-center gap-3">
          <div
            className="h-8 w-8 shrink-0 overflow-hidden rounded-sm bg-gradient-to-br from-surface-container-highest to-surface-container-high"
            aria-hidden
          />
          <div className="text-xs">
            <div className="font-medium text-on-surface">Agent ID: 8842</div>
            <div className="font-mono text-on-surface-variant">SYS.OK</div>
          </div>
        </div>
      </div>
    </nav>
  );
}
