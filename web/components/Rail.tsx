import { Search, Bell, Network, FileClock, Settings } from "lucide-react";

const items = [
  { icon: Search, label: "Investigate", active: true },
  { icon: Bell, label: "Alerts", active: false },
  { icon: Network, label: "Graph", active: false },
  { icon: FileClock, label: "Audit", active: false },
  { icon: Settings, label: "Settings", active: false },
];

export default function Rail() {
  return (
    <aside className="sticky top-0 hidden h-screen w-14 shrink-0 flex-col border-r border-border bg-surface sm:flex">
      <div className="flex h-14 items-center justify-center border-b border-border">
        <div className="flex h-8 w-8 items-center justify-center rounded-sm bg-text text-[10px] font-semibold tracking-wider text-accent">
          H<span className="text-accent">2</span>O
        </div>
      </div>
      <nav className="flex flex-1 flex-col items-center gap-1 py-3">
        {items.map(({ icon: Icon, label, active }) => (
          <button
            key={label}
            aria-label={label}
            title={label}
            disabled={!active}
            className={
              "flex h-10 w-10 items-center justify-center rounded-md transition-colors " +
              (active
                ? "bg-surface-alt text-text"
                : "text-text-muted hover:text-text disabled:hover:text-text-muted")
            }
          >
            <Icon size={18} strokeWidth={1.75} />
          </button>
        ))}
      </nav>
      <div className="flex h-12 items-center justify-center text-[10px] tracking-wider text-text-muted">
        v0.1
      </div>
    </aside>
  );
}
