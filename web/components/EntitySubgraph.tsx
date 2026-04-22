import { Share2 } from "lucide-react";
import type { CaseAssessment, SubgraphNode } from "@/lib/types";

type Pos = { x: number; y: number };
type NodeShape = "circle" | "rect" | "rect-dashed" | "pill" | "diamond";

const POS: Record<string, Pos> = {
  p_jonathan_lim: { x: 80,  y: 115 },
  i_mossack:      { x: 80,  y: 295 },
  c_nielsen:      { x: 420, y: 115 },
  c_nescoll:      { x: 420, y: 205 },
  c_hangon:       { x: 420, y: 295 },
  a_bsi_geneva:   { x: 600, y: 60  },
  j_bvi:          { x: 600, y: 245 },
};

const RECT_W = 150;
const RECT_H = 44;
const CIRCLE_R = 28;
const DIAMOND_RX = 36;
const DIAMOND_RY = 30;

const TYPE_SHAPE: Record<SubgraphNode["type"], NodeShape> = {
  Person: "circle",
  Company: "rect",
  Intermediary: "rect-dashed",
  Jurisdiction: "diamond",
  Address: "pill",
};

const RISK_COLOR = {
  HIGH:   { fill: "#ffdad6", stroke: "#ba1a1a", text: "#93000a", note: "#7a1d1d" },
  MEDIUM: { fill: "#ffdf9a", stroke: "#785a00", text: "#5a4300", note: "#6b4e00" },
  LOW:    { fill: "#dde1ff", stroke: "#00288e", text: "#173bab", note: "#2e4dbe" },
  NONE:   { fill: "#e1e3e4", stroke: "#757684", text: "#191c1d", note: "#444653" },
};

const EDGE_STYLE: Record<string, { stroke: string; dash?: string; label: string }> = {
  RECEIVED_WIRE_FROM: { stroke: "#ba1a1a", dash: "5 3", label: "Received wire from" },
  INTERMEDIARY_OF:    { stroke: "#785a00", label: "Intermediary of" },
  INCORPORATED_IN:    { stroke: "#6f6f82", dash: "2 3", label: "Incorporated in" },
  ROUTED_THROUGH:     { stroke: "#00639b", dash: "5 3", label: "Routed through" },
};
const EDGE_DEFAULT = { stroke: "#9aa0a6", label: "Related" };

const SHAPE_LEGEND: { shape: NodeShape; label: string }[] = [
  { shape: "circle",       label: "Person" },
  { shape: "rect",         label: "Company" },
  { shape: "rect-dashed",  label: "Intermediary" },
  { shape: "pill",         label: "Address / Bank" },
  { shape: "diamond",      label: "Jurisdiction" },
];

function isRectLike(shape: NodeShape): boolean {
  return shape === "rect" || shape === "rect-dashed" || shape === "pill";
}

function nodeEdgePoint(center: Pos, toward: Pos, shape: NodeShape): Pos {
  const dx = toward.x - center.x;
  const dy = toward.y - center.y;
  const len = Math.hypot(dx, dy) || 1;
  const ux = dx / len;
  const uy = dy / len;

  if (shape === "circle") {
    return { x: center.x + ux * CIRCLE_R, y: center.y + uy * CIRCLE_R };
  }
  if (shape === "diamond") {
    const t = 1 / (Math.abs(ux) / DIAMOND_RX + Math.abs(uy) / DIAMOND_RY);
    return { x: center.x + ux * t, y: center.y + uy * t };
  }
  if (shape === "pill") {
    const halfW = RECT_W / 2;
    const halfH = RECT_H / 2;
    const rx = halfH;
    const coreW = halfW - rx;
    if (uy !== 0) {
      const t = halfH / Math.abs(uy);
      if (Math.abs(ux * t) <= coreW) {
        return { x: center.x + ux * t, y: center.y + uy * t };
      }
    }
    const cx = (ux >= 0 ? 1 : -1) * coreW;
    const b = -2 * cx * ux;
    const c = cx * cx - rx * rx;
    const disc = Math.max(0, b * b - 4 * c);
    const t = (-b + Math.sqrt(disc)) / 2;
    return { x: center.x + ux * t, y: center.y + uy * t };
  }
  // rect / rect-dashed
  const halfW = RECT_W / 2;
  const halfH = RECT_H / 2;
  const tx = ux === 0 ? Infinity : halfW / Math.abs(ux);
  const ty = uy === 0 ? Infinity : halfH / Math.abs(uy);
  const t = Math.min(tx, ty);
  return { x: center.x + ux * t, y: center.y + uy * t };
}

function renderNodeShape(shape: NodeShape, palette: typeof RISK_COLOR[keyof typeof RISK_COLOR]) {
  if (shape === "circle") {
    return <circle r={CIRCLE_R} fill={palette.fill} stroke={palette.stroke} strokeWidth={1.5} />;
  }
  if (shape === "diamond") {
    return (
      <polygon
        points={`0,${-DIAMOND_RY} ${DIAMOND_RX},0 0,${DIAMOND_RY} ${-DIAMOND_RX},0`}
        fill={palette.fill}
        stroke={palette.stroke}
        strokeWidth={1.5}
      />
    );
  }
  const rx = shape === "pill" ? RECT_H / 2 : 3;
  const dash = shape === "rect-dashed" ? "5 3" : undefined;
  return (
    <rect
      x={-RECT_W / 2}
      y={-RECT_H / 2}
      width={RECT_W}
      height={RECT_H}
      rx={rx}
      fill={palette.fill}
      stroke={palette.stroke}
      strokeWidth={1.5}
      strokeDasharray={dash}
    />
  );
}

function ShapeSwatch({ shape }: { shape: NodeShape }) {
  const fill = "#eceff1";
  const stroke = "#5a5c66";
  return (
    <svg width={22} height={14} viewBox="-11 -7 22 14" className="shrink-0">
      {shape === "circle" && (
        <circle r={5} fill={fill} stroke={stroke} strokeWidth={1} />
      )}
      {shape === "diamond" && (
        <polygon points="0,-6 8,0 0,6 -8,0" fill={fill} stroke={stroke} strokeWidth={1} />
      )}
      {(shape === "rect" || shape === "rect-dashed") && (
        <rect
          x={-9}
          y={-5}
          width={18}
          height={10}
          rx={1.5}
          fill={fill}
          stroke={stroke}
          strokeWidth={1}
          strokeDasharray={shape === "rect-dashed" ? "2 1.5" : undefined}
        />
      )}
      {shape === "pill" && (
        <rect
          x={-9}
          y={-5}
          width={18}
          height={10}
          rx={5}
          fill={fill}
          stroke={stroke}
          strokeWidth={1}
        />
      )}
    </svg>
  );
}

export default function EntitySubgraph({ subgraph }: { subgraph: CaseAssessment["subgraph"] }) {
  const W = 700;
  const H = 370;

  const focusEdge = subgraph.edges.find((e) => e.kind.includes("WIRE")) ?? subgraph.edges[0];
  const focusCounterparty = subgraph.nodes.find((n) => n.id === focusEdge?.source);

  const presentKinds = Array.from(new Set(subgraph.edges.map((e) => e.kind)));
  const presentShapes = Array.from(new Set(subgraph.nodes.map((n) => TYPE_SHAPE[n.type])));
  const shapeLegend = SHAPE_LEGEND.filter((s) => presentShapes.includes(s.shape));

  return (
    <div className="relative w-full rounded border border-surface-container bg-surface-container-lowest p-6">
      <div className="mb-6 flex items-center justify-between">
        <h3 className="flex items-center gap-2 text-sm font-bold uppercase tracking-wider text-on-surface">
          <Share2 size={16} strokeWidth={1.75} />
          Entity Subgraph Topology
        </h3>
        <div className="flex gap-4 text-xs text-on-surface-variant">
          <div className="flex items-center gap-1.5">
            <span
              className="inline-block h-3 w-3 rounded-sm border"
              style={{ backgroundColor: RISK_COLOR.HIGH.fill, borderColor: RISK_COLOR.HIGH.stroke }}
            />
            High Risk
          </div>
          <div className="flex items-center gap-1.5">
            <span
              className="inline-block h-3 w-3 rounded-sm border"
              style={{ backgroundColor: RISK_COLOR.MEDIUM.fill, borderColor: RISK_COLOR.MEDIUM.stroke }}
            />
            Medium Risk
          </div>
          <div className="flex items-center gap-1.5">
            <span
              className="inline-block h-3 w-3 rounded-sm border"
              style={{ backgroundColor: RISK_COLOR.LOW.fill, borderColor: RISK_COLOR.LOW.stroke }}
            />
            Low Risk
          </div>
        </div>
      </div>

      <div className="grid grid-cols-12 gap-4">
        <div className="col-span-12 flex flex-col overflow-hidden rounded border border-outline-variant/20 bg-surface-container-low/30 lg:col-span-8">
          <svg
            viewBox={`0 0 ${W} ${H}`}
            preserveAspectRatio="xMidYMid meet"
            className="h-96 w-full"
          >
            <defs>
              <marker
                id="arrow"
                viewBox="0 0 10 10"
                refX="8"
                refY="5"
                markerWidth="7"
                markerHeight="7"
                orient="auto-start-reverse"
              >
                <path d="M 0 0 L 10 5 L 0 10 z" fill="#5a5c66" />
              </marker>
            </defs>

            {subgraph.edges.map((e, i) => {
              const a = POS[e.source];
              const b = POS[e.target];
              const srcNode = subgraph.nodes.find((n) => n.id === e.source);
              const tgtNode = subgraph.nodes.find((n) => n.id === e.target);
              if (!a || !b || !srcNode || !tgtNode) return null;
              const style = EDGE_STYLE[e.kind] ?? EDGE_DEFAULT;
              const start = nodeEdgePoint(a, b, TYPE_SHAPE[srcNode.type]);
              const end = nodeEdgePoint(b, a, TYPE_SHAPE[tgtNode.type]);
              return (
                <line
                  key={i}
                  x1={start.x}
                  y1={start.y}
                  x2={end.x}
                  y2={end.y}
                  stroke={style.stroke}
                  strokeWidth={1.4}
                  strokeDasharray={style.dash}
                  markerEnd="url(#arrow)"
                  opacity={0.9}
                />
              );
            })}

            {subgraph.nodes.map((n) => {
              const p = POS[n.id];
              if (!p) return null;
              const palette = RISK_COLOR[n.risk_tier ?? "NONE"];
              const shape = TYPE_SHAPE[n.type];
              const rectLike = isRectLike(shape);
              return (
                <g key={n.id} transform={`translate(${p.x}, ${p.y})`}>
                  {renderNodeShape(shape, palette)}
                  {rectLike ? (
                    <>
                      <text
                        y={n.note ? -4 : 4}
                        textAnchor="middle"
                        fontSize={11}
                        fontWeight={600}
                        fill={palette.text}
                      >
                        {truncate(n.label, 24)}
                      </text>
                      {n.note && (
                        <text y={11} textAnchor="middle" fontSize={9} fill={palette.note}>
                          {truncate(n.note, 26)}
                        </text>
                      )}
                    </>
                  ) : (
                    <>
                      <text
                        y={shape === "circle" ? CIRCLE_R + 14 : DIAMOND_RY + 14}
                        textAnchor="middle"
                        fontSize={11}
                        fontWeight={600}
                        fill={palette.text}
                      >
                        {truncate(n.label, 26)}
                      </text>
                      {n.note && (
                        <text
                          y={shape === "circle" ? CIRCLE_R + 26 : DIAMOND_RY + 26}
                          textAnchor="middle"
                          fontSize={9}
                          fill={palette.note}
                        >
                          {truncate(n.note, 28)}
                        </text>
                      )}
                    </>
                  )}
                </g>
              );
            })}
          </svg>

          <div className="border-t border-outline-variant/20 bg-surface-container-lowest/60 px-4 py-2 text-[10px] text-on-surface-variant">
            <div className="flex flex-wrap items-center gap-x-4 gap-y-1">
              <span className="font-semibold uppercase tracking-wider text-on-surface-variant/80">
                Entity
              </span>
              {shapeLegend.map((s) => (
                <div key={s.shape} className="flex items-center gap-1.5">
                  <ShapeSwatch shape={s.shape} />
                  <span className="whitespace-nowrap">{s.label}</span>
                </div>
              ))}
            </div>
            <div className="mt-1.5 flex flex-wrap items-center gap-x-4 gap-y-1">
              <span className="font-semibold uppercase tracking-wider text-on-surface-variant/80">
                Relation
              </span>
              {presentKinds.map((kind) => {
                const style = EDGE_STYLE[kind] ?? EDGE_DEFAULT;
                return (
                  <div key={kind} className="flex items-center gap-1.5">
                    <svg width={22} height={6} className="shrink-0">
                      <line
                        x1={0}
                        y1={3}
                        x2={22}
                        y2={3}
                        stroke={style.stroke}
                        strokeWidth={1.4}
                        strokeDasharray={style.dash}
                      />
                    </svg>
                    <span className="whitespace-nowrap">{style.label}</span>
                  </div>
                );
              })}
            </div>
          </div>
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
