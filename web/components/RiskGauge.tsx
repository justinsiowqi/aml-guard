"use client";

import { useEffect, useRef, useState } from "react";

export default function RiskGauge({ value, tone = "danger" }: { value: number; tone?: "danger" | "warning" | "success" }) {
  // animate from 0 → value on mount
  const [display, setDisplay] = useState(0);
  const ranRef = useRef(false);

  useEffect(() => {
    if (ranRef.current) return;
    ranRef.current = true;
    const start = performance.now();
    const duration = 850;
    const from = 0;
    const to = Math.max(0, Math.min(1, value));

    function tick(now: number) {
      const p = Math.min(1, (now - start) / duration);
      const eased = 1 - Math.pow(1 - p, 3);
      setDisplay(from + (to - from) * eased);
      if (p < 1) requestAnimationFrame(tick);
    }
    requestAnimationFrame(tick);
  }, [value]);

  const size = 132;
  const stroke = 12;
  const r = (size - stroke) / 2;
  const c = Math.PI * r; // semicircle circumference
  const offset = c * (1 - display);

  const colorMap = {
    danger: "#991b1b",
    warning: "#92400e",
    success: "#166534",
  };
  const color = colorMap[tone];

  return (
    <div className="relative flex h-[84px] w-[132px] items-end justify-center">
      <svg width={size} height={size / 2 + 6} viewBox={`0 0 ${size} ${size / 2 + 6}`} aria-hidden>
        <path
          d={`M ${stroke / 2},${size / 2} A ${r},${r} 0 0 1 ${size - stroke / 2},${size / 2}`}
          fill="none"
          stroke="#e5e5e5"
          strokeWidth={stroke}
          strokeLinecap="round"
        />
        <path
          d={`M ${stroke / 2},${size / 2} A ${r},${r} 0 0 1 ${size - stroke / 2},${size / 2}`}
          fill="none"
          stroke={color}
          strokeWidth={stroke}
          strokeLinecap="round"
          strokeDasharray={c}
          strokeDashoffset={offset}
        />
      </svg>
      <div className="pointer-events-none absolute inset-x-0 bottom-0 flex flex-col items-center">
        <span className="tabular font-display text-3xl leading-none text-text">
          {display.toFixed(2)}
        </span>
        <span className="text-[10px] uppercase tracking-[0.16em] text-text-muted">
          risk score
        </span>
      </div>
    </div>
  );
}
