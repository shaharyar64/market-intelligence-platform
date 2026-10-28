"use client";

interface TopicItem {
  topic: string;
  total_comments: number;
  positive_comments: number;
  negative_comments: number;
  neutral_comments?: number; // Optional if backend sends it
}

interface Props {
  data: TopicItem[];
}

export default function TopicSentimentGlass({ data }: Props) {
  return (
    <div
      className="
      rounded-2xl
      p-6
      bg-white/5
      backdrop-blur-xl
      border border-white/10
      shadow-[0_8px_32px_0_rgba(0,0,0,0.35)]
    "
    >
      <h3 className="text-lg font-semibold text-white mb-6">
        🧠 Topic Sentiment Breakdown
      </h3>

      <div className="space-y-8">
        {data?.map((item, index) => {
          const total = item.total_comments || 0;

          const positive = item.positive_comments || 0;
          const negative = item.negative_comments || 0;

          // If backend sends neutral, use it.
          // Otherwise calculate it safely.
          const neutral =
            item.neutral_comments !== undefined
              ? item.neutral_comments
              : total - positive - negative;

          const positivePercent =
            total > 0 ? (positive / total) * 100 : 0;

          const neutralPercent =
            total > 0 ? (neutral / total) * 100 : 0;

          const negativePercent =
            total > 0 ? (negative / total) * 100 : 0;

          return (
            <div key={index}>
              {/* Header */}
              <div className="flex justify-between mb-3">
                <span className="text-white font-medium">
                  {item.topic}
                </span>
                <span className="text-slate-400 text-sm">
                  {total} reviews
                </span>
              </div>

              {/* Stacked Bar */}
              <div className="w-full h-9 flex rounded-lg overflow-hidden bg-white/10">
                {/* Positive */}
                <div
                  className="bg-emerald-500 flex items-center justify-center text-xs font-semibold text-white transition-all duration-700"
                  style={{ width: `${positivePercent}%` }}
                >
                  {positivePercent > 8
                    ? `${positivePercent.toFixed(0)}%`
                    : ""}
                </div>

                {/* Neutral */}
                <div
                  className="bg-slate-500 flex items-center justify-center text-xs font-semibold text-white transition-all duration-700"
                  style={{ width: `${neutralPercent}%` }}
                >
                  {neutralPercent > 8
                    ? `${neutralPercent.toFixed(0)}%`
                    : ""}
                </div>

                {/* Negative */}
                <div
                  className="bg-red-500 flex items-center justify-center text-xs font-semibold text-white transition-all duration-700"
                  style={{ width: `${negativePercent}%` }}
                >
                  {negativePercent > 8
                    ? `${negativePercent.toFixed(0)}%`
                    : ""}
                </div>
              </div>

              {/* Footer counts */}
              <div className="flex justify-between mt-3 text-xs">
                <span className="text-emerald-400">
                  Positive: {positive}
                </span>

                <span className="text-slate-400">
                  Neutral: {neutral}
                </span>

                <span className="text-red-400">
                  Negative: {negative}
                </span>
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
}