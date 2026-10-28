"use client";

interface SentimentData {
  very_positive: number;
  positive: number;
  neutral: number;
  negative: number;
  very_negative: number;
}

interface Props {
  data: SentimentData;
}

export default function SentimentGlassBar({ data }: Props) {
  const segments = [
    {
      label: "Very Positive",
      value: data?.very_positive || 0,
      color: "bg-emerald-600",
      dot: "bg-emerald-500",
    },
    {
      label: "Positive",
      value: data?.positive || 0,
      color: "bg-emerald-400",
      dot: "bg-green-400",
    },
    {
      label: "Neutral",
      value: data?.neutral || 0,
      color: "bg-slate-500",
      dot: "bg-slate-400",
    },
    {
      label: "Negative",
      value: data?.negative || 0,
      color: "bg-orange-500",
      dot: "bg-orange-400",
    },
    {
      label: "Very Negative",
      value: data?.very_negative || 0,
      color: "bg-red-600",
      dot: "bg-red-500",
    },
  ];

  const total = segments.reduce((sum, s) => sum + s.value, 0);

  // Calculate normalized percentages
  const normalized = segments.map((s) => {
    const percent = total > 0 ? (s.value / total) * 100 : 0;
    return {
      ...s,
      percent,
    };
  });

  return (
    <div
      className="
      relative rounded-2xl p-6
      bg-white/5 backdrop-blur-xl
      border border-white/10
      shadow-[0_8px_32px_0_rgba(0,0,0,0.35)]
      overflow-hidden
    "
    >
      <div className="absolute inset-0 bg-gradient-to-br from-white/5 to-transparent pointer-events-none" />

      <h3 className="relative text-lg font-semibold text-white mb-6">
        Sentiment Analysis
      </h3>

      {/* Stacked Bar */}
      <div className="relative w-full h-10 rounded-xl overflow-hidden flex bg-white/10">
        {normalized.map((seg, i) =>
          seg.percent > 0 ? (
            <div
              key={i}
              className={`flex items-center justify-center text-xs font-semibold text-white transition-all duration-700 ${seg.color}`}
              style={{ width: `${seg.percent}%` }}
            >
              {/* Show percentage only if wide enough */}
              {seg.percent > 6
                ? `${seg.percent.toFixed(0)}%`
                : ""}
            </div>
          ) : null
        )}
      </div>

      {/* Legend */}
      <div className="relative flex flex-wrap gap-4 mt-4 text-sm">
        {normalized.map((seg, i) => (
          <div key={i} className="flex items-center gap-2 text-slate-300">
            <span className={`w-3 h-3 rounded-full ${seg.dot}`} />
            <span>
              {seg.label}:{" "}
              {seg.percent.toFixed(1)}%
            </span>
          </div>
        ))}
      </div>
    </div>
  );
}