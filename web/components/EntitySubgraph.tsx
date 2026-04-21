import { Share2 } from "lucide-react";
import type { CaseAssessment, SubgraphNode } from "@/lib/types";

const POS: Record<string, { x: number; y: number }> = {
  p_jonathan_lim: { x: 40, y: 50 },
  c_nielsen:      { x: 190, y: 40 },
  c_nescoll:      { x: 190, y: 105 },
  c_hangon:       { x: 190, y: 170 },
  i_mossack:      { x: 340, y: 40 },
  j_bvi:          { x: 340, y: 170 },
  a_bsi_geneva:   { x: 40, y: 170 },
};

const TYPE_SHAPE: Record<SubgraphNode["type"], "circle" | "rect" | "diamond"> = {
  Person: "circle",
  Company: "rect",
  Intermediary: "rect",
  Jurisdiction: "diamond",
  Address: "rect",
};

const RISK_COLOR = {
  HIGH:   { fill: "#ffdad6", stroke: "#ba1a1a", text: "#93000a" },
  MEDIUM: { fill: "#ffdf9a", stroke: "#785a00", text: "#5a4300" },
  LOW:    { fill: "#dde1ff", stroke: "#00288e", text: "#173bab" },
  NONE:   { fill: "#e1e3e4", stroke: "#757684", text: "#191c1d" },
};

export default function EntitySubgraph({ subgraph }: { subgraph: CaseAssessment["subgraph"] }) {
  const W = 420;
  const H = 230;

  const focusEdge = subgraph.edges.find((e) => e.kind.includes("WIRE")) ?? subgraph.edges[0];
  const focusCounterparty = subgraph.nodes.find((n) => n.id === focusEdge?.source);

  return (
    <div className="relative w-full rounded border border-surface-container bg-surface-container-lowest p-6">
      <div className="mb-6 flex items-center justify-between">
        <h3 className="flex items-center gap-2 text-sm font-bold uppercase tracking-wider text-on-surface">
          <Share2 size={16} strokeWidth={1.75} />
          Entity Subgraph Topology
        </h3>
        <div className="flex gap-4 text-xs">
          <div className="flex items-center gap-1.5">
            <div className="h-2 w-2 rounded-full bg-error" /> High Risk
          </div>
          <div className="flex items-center gap-1.5">
            <div className="h-2 w-2 rounded-full bg-primary" /> Focus Entity
          </div>
          <div className="flex items-center gap-1.5">
            <div className="h-2 w-2 rounded-full bg-outline" /> Standard
          </div>
        </div>
      </div>

      <div className="grid grid-cols-12 gap-4">
        <div className="col-span-12 flex h-72 items-center justify-center overflow-hidden rounded border border-outline-variant/20 bg-surface-container-low/30 lg:col-span-8">
        <svg
          viewBox={`0 0 ${W} ${H}`}
          preserveAspectRatio="xMidYMid meet"
          className="h-full w-full"
        >
          <defs>
            <marker
              id="arrow"
              viewBox="0 0 10 10"
              refX="9"
              refY="5"
              markerWidth="6"
              markerHeight="6"
              orient="auto-start-reverse"
            >
              <path d="M 0 0 L 10 5 L 0 10 z" fill="#757684" />
            </marker>
          </defs>

          {subgraph.edges.map((e, i) => {
            const a = POS[e.source];
            const b = POS[e.target];
            if (!a || !b) return null;
            const midX = (a.x + b.x) / 2;
            const midY = (a.y + b.y) / 2;
            const sourceNode = subgraph.nodes.find((n) => n.id === e.source);
            const targetNode = subgraph.nodes.find((n) => n.id === e.target);
            const isHighRisk =
              sourceNode?.risk_tier === "HIGH" && targetNode?.risk_tier === "HIGH";
            return (
              <g key={i}>
                <line
                  x1={a.x}
                  y1={a.y}
                  x2={b.x}
                  y2={b.y}
                  stroke={isHighRisk ? "#ba1a1a" : "#c4c5d5"}
                  strokeWidth={isHighRisk ? 1.5 : 1}
                  strokeDasharray={isHighRisk ? "4 2" : undefined}
                  markerEnd="url(#arrow)"
                />
                <text x={midX} y={midY - 3} textAnchor="middle" fontSize={8} fill="#444653" className="font-mono">
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
                  <rect
                    x={-34}
                    y={-14}
                    width={68}
                    height={28}
                    rx={2}
                    fill={palette.fill}
                    stroke={palette.stroke}
                    strokeWidth={1.5}
                  />
                )}
                {shape === "diamond" && (
                  <polygon
                    points="0,-18 22,0 0,18 -22,0"
                    fill={palette.fill}
                    stroke={palette.stroke}
                    strokeWidth={1.5}
                  />
                )}
                <text
                  y={shape === "rect" ? 0 : 35}
                  textAnchor="middle"
                  alignmentBaseline="middle"
                  fontSize={shape === "rect" ? 8.5 : 9}
                  fontWeight={600}
                  fill={palette.text}
                >
                  {truncate(n.label, shape === "rect" ? 14 : 20)}
                </text>
                {n.note && shape !== "rect" && (
                  <text y={48} textAnchor="middle" fontSize={7.5} fill="#444653">
                    {n.note}
                  </text>
                )}
              </g>
            );
          })}
        </svg>
        </div>

        {focusCounterparty && (
          <div className="col-span-12 rounded border border-outline-variant/30 bg-surface-container-lowest p-4 lg:col-span-4">
            <div className="mb-2 border-b border-surface-container-high pb-1 text-[10px] font-bold uppercase tracking-wider text-on-surface-variant">
              Connection Focus
            </div>
            <div className="mb-1 flex items-baseline justify-between gap-2">
              <span className="min-w-0 truncate text-sm font-semibold text-[#191c1d]">
                {focusCounterparty.label}
              </span>
              <span className="shrink-0 font-mono text-[11px] text-[#ba1a1a]">Risk: 0.89</span>
            </div>
            <div className="mb-3 text-xs text-[#444653]">
              Directional flow: <span className="font-medium text-[#191c1d]">Outbound</span>
            </div>
            <div className="font-mono text-base font-bold text-[#191c1d]">SGD 1,976,600</div>
            <div className="mt-1 text-[11px] italic text-[#444653]">
              Via 4 successive wire transfers.
            </div>
          </div>
        )}
      </div>
    </div>
  );
}

function truncate(s: string, n: number): string {
  return s.length > n ? s.slice(0, n - 1) + "…" : s;
}
