export default function Sparkline({
  data,
  width = 220,
  height = 36,
  tone = "danger",
}: {
  data: number[];
  width?: number;
  height?: number;
  tone?: "danger" | "warning" | "success" | "neutral";
}) {
  if (!data.length) return null;
  const max = Math.max(...data, 1);
  const stepX = data.length > 1 ? width / (data.length - 1) : width;
  const points = data
    .map((v, i) => `${(i * stepX).toFixed(2)},${(height - (v / max) * (height - 4) - 2).toFixed(2)}`)
    .join(" ");

  const colorMap = {
    danger: "#991b1b",
    warning: "#92400e",
    success: "#166534",
    neutral: "#737373",
  };
  const color = colorMap[tone];

  return (
    <svg width={width} height={height} viewBox={`0 0 ${width} ${height}`} aria-hidden>
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
