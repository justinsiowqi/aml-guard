import { Share2 } from "lucide-react";
import type { CaseAssessment, ConnectionFocus, SubgraphNode } from "@/lib/types";

type Pos = { x: number; y: number };
type NodeShape = "circle" | "rect" | "rect-dashed" | "pill" | "diamond";

function pickSeed(
  nodes: SubgraphNode[],
  edges: { source: string; target: string }[],
): SubgraphNode {
  const degree = new Map<string, number>();
  for (const e of edges) {
    degree.set(e.source, (degree.get(e.source) ?? 0) + 1);
    degree.set(e.target, (degree.get(e.target) ?? 0) + 1);
  }
  return nodes.slice().sort((a, b) => (degree.get(b.id) ?? 0) - (degree.get(a.id) ?? 0))[0];
}

function spreadHoriz(
  nodes: SubgraphNode[],
  positions: Record<string, Pos>,
  width: number,
  y: number,
): void {
  if (nodes.length === 0) return;
  if (nodes.length === 1) {
    positions[nodes[0].id] = { x: width / 2, y };
    return;
  }
  const margin = width * 0.08;
  const available = width - 2 * margin;
  const step = available / (nodes.length - 1);
  nodes.forEach((n, i) => {
    positions[n.id] = { x: margin + i * step, y };
  });
}

/**
 * Three-band hierarchical layout for AML investigation:
 *   row 0 (top)    — Officers (Persons): who controls the seed
 *   row 1 (middle) — Seed entity, with metadata badges; intermediary just below
 *   row 2 (bottom) — 2-hop network: shells controlled by the same officers
 *                    and/or set up by the same intermediary
 *
 * Reads top-down as "who → what → how", which matches the analyst's
 * mental model better than a radial layout.
 */
function computeHierarchicalLayout(
  nodes: SubgraphNode[],
  edges: { source: string; target: string }[],
  width: number,
  height: number,
): Record<string, Pos> {
  const positions: Record<string, Pos> = {};
  if (nodes.length === 0) return positions;

  const seed = pickSeed(nodes, edges);

  const oneHopIds = new Set<string>();
  for (const e of edges) {
    if (e.source === seed.id) oneHopIds.add(e.target);
    else if (e.target === seed.id) oneHopIds.add(e.source);
  }

  const officersAndPeers: SubgraphNode[] = [];
  const intermediaries: SubgraphNode[] = [];
  for (const n of nodes) {
    if (n.id === seed.id || !oneHopIds.has(n.id)) continue;
    if (n.type === "Intermediary") intermediaries.push(n);
    else officersAndPeers.push(n);
  }
  const twoHop = nodes.filter((n) => n.id !== seed.id && !oneHopIds.has(n.id));

  const cx = width / 2;
  const rowOfficers      = height * 0.16;
  const rowSeed          = height * 0.42;
  const rowIntermediary  = height * 0.62;
  const rowTwoHop        = height * 0.86;

  positions[seed.id] = { x: cx, y: rowSeed };
  spreadHoriz(officersAndPeers, positions, width, rowOfficers);
  spreadHoriz(intermediaries,    positions, width, rowIntermediary);
  spreadHoriz(twoHop,            positions, width, rowTwoHop);

  return positions;
}

const RECT_W = 110;
const RECT_H = 38;
const CIRCLE_R = 24;
const DIAMOND_RX = 30;
const DIAMOND_RY = 26;

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

const FOCUS_RISK_PILL: Record<"HIGH" | "MEDIUM" | "LOW", string> = {
  HIGH:   "bg-error-container text-on-error-container",
  MEDIUM: "bg-secondary-fixed text-on-secondary-fixed",
  LOW:    "bg-primary-fixed text-on-primary-fixed",
};

export default function EntitySubgraph({
  subgraph,
  connectionFocus,
}: {
  subgraph: CaseAssessment["subgraph"];
  connectionFocus: ConnectionFocus | null;
}) {
  const W = 1100;
  const H = 680;

  const POS = computeHierarchicalLayout(subgraph.nodes, subgraph.edges, W, H);
  const seed = subgraph.nodes.length > 0 ? pickSeed(subgraph.nodes, subgraph.edges) : null;

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
            className="h-[30rem] w-full"
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

            {seed?.metadata && POS[seed.id] && (
              <g transform={`translate(${POS[seed.id].x}, ${POS[seed.id].y})`}>
                {seed.metadata.jurisdiction && (
                  <text
                    y={RECT_H / 2 + 16}
                    textAnchor="middle"
                    fontSize={11}
                    fontWeight={600}
                    fontStyle="italic"
                    fill="#5a4300"
                  >
                    {truncate(seed.metadata.jurisdiction, 36)}
                  </text>
                )}
                {seed.metadata.address && (
                  <text
                    y={RECT_H / 2 + 32}
                    textAnchor="middle"
                    fontSize={10}
                    fill="#6b6f78"
                  >
                    {truncate(seed.metadata.address, 40)}
                  </text>
                )}
              </g>
            )}
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

        {connectionFocus && (
          <div className="col-span-12 rounded border border-outline-variant/30 bg-surface-container-lowest p-4 lg:col-span-4">
            <div className="mb-3 border-b border-surface-container-high pb-1 text-[10px] font-bold uppercase tracking-wider text-on-surface-variant">
              Connection Focus
            </div>

            <div className="mb-2 flex flex-wrap items-center gap-1.5">
              <span
                className={`rounded-sm px-1.5 py-0.5 text-[10px] font-bold uppercase tracking-wider ${FOCUS_RISK_PILL[connectionFocus.risk_tier]}`}
              >
                {connectionFocus.risk_tier}
              </span>
              <span className="text-[10px] uppercase tracking-wider text-on-surface-variant/80">
                {connectionFocus.counterparty_type}
              </span>
            </div>
            <div className="mb-4 break-words text-base font-bold leading-snug text-[#191c1d]">
              {connectionFocus.counterparty_label}
            </div>

            <div className="border-t border-surface-container-high pt-3">
              <div className="text-[10px] font-semibold uppercase tracking-wider text-on-surface-variant">
                Linked via
              </div>
              <div className="mt-1 break-words text-sm font-medium text-[#191c1d]">
                {connectionFocus.relationship_summary}
              </div>
              <div className="mt-1.5 text-[11px] text-[#444653]">
                {connectionFocus.link_count === 1
                  ? "1 graph link"
                  : `${connectionFocus.link_count} graph links`}
              </div>
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
