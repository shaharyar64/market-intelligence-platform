"use client";

interface BankItem {
  bank: string;
  total_reviews: number;
  positive_reviews: number;
  negative_reviews: number;
}

interface Props {
  data: BankItem[];
}

export default function BankSentimentGlass({ data }: Props) {
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
        🏦 Bank Sentiment Breakdown
      </h3>

      <div className="space-y-8 max-h-[500px] overflow-y-auto pr-2">
        {data?.map((item, index) => {
          const total = item.total_reviews || 0;

          const positive = item.positive_reviews || 0;
          const negative = item.negative_reviews || 0;
          const neutral = total - positive - negative;

          const positivePercent =
            total > 0 ? (positive / total) * 100 : 0;

          const negativePercent =
            total > 0 ? (negative / total) * 100 : 0;

          const neutralPercent =
            total > 0 ? (neutral / total) * 100 : 0;

          return (
            <div key={index}>
              {/* Header */}
              <div className="flex justify-between items-center mb-3">
                <span className="text-white font-medium truncate max-w-[70%]">
                  {item.bank}
                </span>

                <span className="text-slate-400 text-sm">
                  {total} reviews
                </span>
              </div>

              {/* Stacked Sentiment Bar */}
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

              {/* Footer Stats */}
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