interface RankingItem {
  outlet: string;
  brand: string;
  rating: number;
  total_reviews: number;
  top_positive_topic?: string;
  top_negative_topic?: string;
}

interface Props {
  title: string;
  type: "top" | "bottom";
  data: RankingItem[];
}

const countFormatter = new Intl.NumberFormat("en-US", { notation: "compact", maximumFractionDigits: 1 });

export default function OutletRankingTable({ title, type, data }: Props) {
  const topicHeading = type === "top" ? "Top positive topic" : "Top issue";
  const titleId = `${type}-${title.replace(/\s+/g, "-").toLowerCase()}-title`;

  return (
    <section className="chart-card overflow-hidden rounded-2xl" aria-labelledby={titleId}>
      <div className="flex items-start justify-between gap-3 p-4 sm:p-6">
        <div>
          <h3 id={titleId} style={{ color: "var(--title-tx)" }} className="text-base font-semibold">{title}</h3>
          <p style={{ color: "var(--muted-tx)" }} className="mt-1 text-xs">
            {data.length} {data.length === 1 ? "outlet" : "outlets"} ranked by customer rating
          </p>
        </div>
        <span
          className="rounded-full px-2.5 py-1 text-xs font-semibold"
          style={type === "top"
            ? { background: "var(--fi-growth-soft)", color: "var(--fi-growth-tx)" }
            : { background: "rgba(244, 63, 94, 0.12)", color: "var(--fi-danger-tx)" }}
        >
          {type === "top" ? "Highest rated" : "Needs attention"}
        </span>
      </div>

      {data.length === 0 ? (
        <p style={{ color: "var(--muted-tx)" }} className="border-t border-[var(--card-bd)] px-6 py-10 text-center text-sm">
          No outlets match the current filters.
        </p>
      ) : (
        <div className="overflow-x-auto border-t border-[var(--card-bd)]">
          <table className="w-full min-w-[720px] text-left text-sm">
            <caption className="sr-only">{title}</caption>
            <thead style={{ background: "var(--card-bg-2)", color: "var(--muted-tx)" }} className="sticky top-0 z-10 text-xs">
              <tr>
                <th scope="col" className="w-14 px-4 py-3 font-semibold">Rank</th>
                <th scope="col" className="px-4 py-3 font-semibold">Outlet</th>
                <th scope="col" className="px-4 py-3 font-semibold">Brand</th>
                <th scope="col" className="px-4 py-3 font-semibold">Rating</th>
                <th scope="col" className="px-4 py-3 font-semibold">Reviews</th>
                <th scope="col" className="px-4 py-3 font-semibold">{topicHeading}</th>
              </tr>
            </thead>
            <tbody style={{ color: "var(--body-tx)" }}>
              {data.map((item, index) => (
                <tr key={`${item.outlet}-${item.brand}-${index}`} className="border-t border-[var(--card-bd)] transition-colors hover:bg-[var(--nav-hover-bg)]">
                  <td className="px-4 py-3 tabular-nums" style={{ color: "var(--muted-tx)" }}>{index + 1}</td>
                  <td className="max-w-52 truncate px-4 py-3 font-medium" style={{ color: "var(--title-tx)" }} title={item.outlet}>{item.outlet}</td>
                  <td className="px-4 py-3">{item.brand}</td>
                  <td className="px-4 py-3">
                    <span className="inline-flex rounded-full px-2.5 py-1 text-xs font-semibold tabular-nums" style={type === "top"
                      ? { background: "var(--fi-growth-soft)", color: "var(--fi-growth-tx)" }
                      : { background: "rgba(244, 63, 94, 0.12)", color: "var(--fi-danger-tx)" }}>
                      {item.rating.toFixed(1)} / 5
                    </span>
                  </td>
                  <td className="px-4 py-3 tabular-nums">{countFormatter.format(item.total_reviews)}</td>
                  <td className="max-w-64 truncate px-4 py-3" title={type === "top" ? item.top_positive_topic : item.top_negative_topic}>
                    {type === "top" ? item.top_positive_topic || "—" : item.top_negative_topic || "—"}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </section>
  );
}
