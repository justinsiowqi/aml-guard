import type { CaseAssessment, SubgraphNode } from "@/lib/types";

/**
 * Hand-laid positions, keyed by node id in mocks/nielsen-enterprises.json.
 * Intentional layout: Jonathan Lim (top-left subject), three BVI shells in
 * a vertical stack middle, Mossack Fonseca hub top-right, BVI jurisdiction
 * + BSI Geneva anchoring the bottom.
 */
const POS: Record<string, { x: number; y: number }> = {
  p_jonathan_lim: { x: 40,  y: 50 },
  c_nielsen:      { x: 190, y: 40 },
  c_nescoll:      { x: 190, y: 105 },
  c_hangon:       { x: 190, y: 170 },
  i_mossack:      { x: 340, y: 40 },
  j_bvi:          { x: 340, y: 170 },
  a_bsi_geneva:   { x: 40,  y: 170 },
};

const TYPE_SHAPE: Record<SubgraphNode["type"], "circle" | "rect" | "diamond"> = {
  Person: "circle",
  Company: "rect",
  Intermediary: "rect",
  Jurisdiction: "diamond",
  Address: "rect",
};

const RISK_COLOR = {
  HIGH: { fill: "#fef2f2", stroke: "#991b1b", text: "#991b1b" },
  MEDIUM: { fill: "#fffbeb", stroke: "#92400e", text: "#92400e" },
  LOW: { fill: "#f0fdf4", stroke: "#166534", text: "#166534" },
  NONE: { fill: "#fafafa", stroke: "#e5e5e5", text: "#171717" },
};

export default function EntitySubgraph({ subgraph }: { subgraph: CaseAssessment["subgraph"] }) {
  const W = 420;
  const H = 230;

  return (
    <div>
      <div className="mb-3 flex items-baseline justify-between">
        <h3 className="font-display text-2xl text-text">Entity subgraph</h3>
        <span className="text-[11px] uppercase tracking-[0.14em] text-text-muted">
          {subgraph.nodes.length} nodes · {subgraph.edges.length} edges
        </span>
      </div>
      <div className="rounded-md border border-border bg-surface p-3">
        <svg viewBox={`0 0 ${W} ${H}`} className="h-auto w-full">
          <defs>
            <marker id="arrow" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="6" markerHeight="6" orient="auto-start-reverse">
              <path d="M 0 0 L 10 5 L 0 10 z" fill="#737373" />
            </marker>
          </defs>

          {subgraph.edges.map((e, i) => {
            const a = POS[e.source];
            const b = POS[e.target];
            if (!a || !b) return null;
            const midX = (a.x + b.x) / 2;
            const midY = (a.y + b.y) / 2;
            return (
              <g key={i}>
                <line
                  x1={a.x}
                  y1={a.y}
                  x2={b.x}
                  y2={b.y}
                  stroke="#d4d4d4"
                  strokeWidth={1}
                  markerEnd="url(#arrow)"
                />
                <text
                  x={midX}
                  y={midY - 3}
                  textAnchor="middle"
                  className="font-mono"
                  fontSize={8}
                  fill="#737373"
                >
                  {e.kind.toLowerCase()}
                </text>
              </g>
            );
          })}

          {subgraph.nodes.map((n) => {
            const p = POS[n.id];
            if (!p) return null;
            const palette = RISK_COLOR[n.risk_tier ?? "NONE"];
            const shape = TYPE_SHAPE[n.type];
            return (
              <g key={n.id} transform={`translate(${p.x}, ${p.y})`}>
                {shape === "circle" && (
                  <circle r={18} fill={palette.fill} stroke={palette.stroke} strokeWidth={1.5} />
                )}
                {shape === "rect" && (
                  <rect x={-34} y={-14} width={68} height={28} rx={3} fill={palette.fill} stroke={palette.stroke} strokeWidth={1.5} />
                )}
                {shape === "diamond" && (
                  <polygon points="0,-18 22,0 0,18 -22,0" fill={palette.fill} stroke={palette.stroke} strokeWidth={1.5} />
                )}
                <text
                  y={shape === "rect" ? 0 : 35}
                  textAnchor="middle"
                  alignmentBaseline="middle"
                  fontSize={shape === "rect" ? 8.5 : 9}
                  fontWeight={500}
                  fill={palette.text}
                >
                  {truncate(n.label, shape === "rect" ? 14 : 20)}
                </text>
                {n.note && shape !== "rect" && (
                  <text
                    y={shape === "circle" ? 48 : 48}
                    textAnchor="middle"
                    fontSize={7.5}
                    fill="#737373"
                  >
                    {n.note}
                  </text>
                )}
              </g>
            );
          })}
        </svg>

        <div className="mt-2 flex flex-wrap gap-3 border-t border-border pt-2 text-[10px] text-text-muted">
          <LegendSwatch tone="HIGH" label="high risk" />
          <LegendSwatch tone="MEDIUM" label="medium" />
          <LegendSwatch tone="NONE" label="unrated" />
        </div>
      </div>
    </div>
  );
}

function LegendSwatch({ tone, label }: { tone: keyof typeof RISK_COLOR; label: string }) {
  const p = RISK_COLOR[tone];
  return (
    <span className="inline-flex items-center gap-1.5">
      <span className="inline-block h-2.5 w-2.5 rounded-sm" style={{ background: p.fill, border: `1px solid ${p.stroke}` }} />
      {label}
    </span>
  );
}

function truncate(s: string, n: number): string {
  return s.length > n ? s.slice(0, n - 1) + "…" : s;
}
