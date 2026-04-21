export type SparklineTone = "error" | "warning" | "success" | "neutral";

export default function Sparkline({
  data,
  width = 220,
  height = 36,
  tone = "error",
}: {
  data: number[];
  width?: number;
  height?: number;
  tone?: SparklineTone;
}) {
  if (!data.length) return null;
  const max = Math.max(...data, 1);
  const stepX = data.length > 1 ? width / (data.length - 1) : width;
  const points = data
    .map((v, i) => `${(i * stepX).toFixed(2)},${(height - (v / max) * (height - 4) - 2).toFixed(2)}`)
    .join(" ");

  const colorMap: Record<SparklineTone, string> = {
    error: "#ba1a1a",
    warning: "#785a00",
    success: "#00288e",
    neutral: "#757684",
  };
  const color = colorMap[tone];

  return (
    <svg width="100%" height={height} viewBox={`0 0 ${width} ${height}`} preserveAspectRatio="none" aria-hidden>
      <polyline
        fill="none"
        stroke={color}
        strokeWidth={1.5}
        strokeLinecap="round"
        strokeLinejoin="round"
        points={points}
      />
      {data.map((v, i) => (
        <circle
          key={i}
          cx={(i * stepX).toFixed(2)}
          cy={(height - (v / max) * (height - 4) - 2).toFixed(2)}
          r={v > 0 ? 2 : 0}
          fill={color}
        />
      ))}
    </svg>
  );
}
