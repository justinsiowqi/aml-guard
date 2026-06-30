import { Bell, Settings, Search } from "lucide-react";

export default function TopHeader({
  caseId,
  jurisdiction,
}: {
  caseId?: string;
  jurisdiction?: string;
}) {
  return (
    <header className="z-50 flex h-16 w-full shrink-0 items-center justify-between border-b border-outline-variant/20 bg-background/80 px-6 backdrop-blur-md">
      <div className="flex items-center gap-4">
        <h2 className="text-lg font-black tracking-tighter text-on-surface">Forensic Monograph</h2>
        {caseId && (
          <>
            <div className="h-4 w-px bg-outline-variant/40" />
            <div className="flex items-center gap-2 text-sm text-on-surface-variant">
              <span className="font-mono">ID: {caseId}</span>
              {jurisdiction && (
                <span className="rounded-sm bg-surface-container px-1.5 py-0.5 font-mono text-xs">
                  {jurisdiction}
                </span>
              )}
            </div>
          </>
        )}
      </div>

      <div className="flex items-center gap-4">
        <div className="flex overflow-hidden rounded border border-outline-variant/20 bg-surface-container-low">
          <input
            type="text"
            placeholder="Search entity…"
            className="w-48 border-none bg-transparent px-3 py-1.5 text-sm placeholder:text-on-surface-variant/50 focus:outline-none focus:ring-0"
          />
          <button
            type="button"
            aria-label="Search"
            className="px-2 text-on-surface-variant transition-colors duration-200 hover:bg-surface-container hover:text-on-surface"
          >
            <Search size={16} strokeWidth={1.75} />
          </button>
        </div>

        <div className="flex items-center gap-2">
          <button
            type="button"
            aria-label="Notifications"
            className="rounded p-1.5 text-on-surface-variant transition-colors duration-200 hover:bg-surface-container hover:text-on-surface"
          >
            <Bell size={18} strokeWidth={1.75} />
          </button>
          <button
            type="button"
            aria-label="Settings"
            className="rounded p-1.5 text-on-surface-variant transition-colors duration-200 hover:bg-surface-container hover:text-on-surface"
          >
            <Settings size={18} strokeWidth={1.75} />
          </button>
        </div>

        <div
          className="h-8 w-8 overflow-hidden rounded-sm border border-outline-variant/20 bg-gradient-to-br from-surface-container-highest to-surface-container-high"
          aria-label="Investigator profile"
        />
      </div>
    </header>
  );
}
