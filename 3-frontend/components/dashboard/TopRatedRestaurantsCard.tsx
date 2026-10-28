"use client";

type Restaurant = {
  name: string;
  rating: number;
  total_reviews: number;
  google_maps_url: string;
};

type Props = {
  title?: string;
  highRated?: Restaurant[];
  lowRated?: Restaurant[];
};

export default function TopRatedRestaurantsCard({
  title = "Restaurant Ratings",
  highRated = [],
  lowRated = [],
}: Props) {
  return (
    <div className="rounded-2xl p-6 bg-white/5 border border-white/10 backdrop-blur-xl shadow-xl">
      <h3 className="text-lg font-semibold text-white mb-6">{title}</h3>

      <div className="grid md:grid-cols-2 gap-8">
        {/* Top Rated */}
        <div>
          <h4 className="text-sm font-semibold text-green-400 mb-4">
            ⭐ Top Rated
          </h4>

          <div className="space-y-3">
            {highRated.map((r, i) => (
              <a
                key={i}
                href={r.google_maps_url}
                target="_blank"
                rel="noopener noreferrer"
                className="flex items-center justify-between p-3 rounded-xl bg-white/5 hover:bg-white/10 transition"
              >
                <div>
                  <p className="text-sm text-white font-medium">{r.name}</p>
                  <p className="text-xs text-slate-400">
                    {r.total_reviews} reviews
                  </p>
                </div>

                <div className="text-green-400 font-semibold">
                  {r.rating.toFixed(1)}
                </div>
              </a>
            ))}
          </div>
        </div>

        {/* Lowest Rated */}
        <div>
          <h4 className="text-sm font-semibold text-red-400 mb-4">
            ⚠ Lowest Rated
          </h4>

          <div className="space-y-3">
            {lowRated.map((r, i) => (
              <a
                key={i}
                href={r.google_maps_url}
                target="_blank"
                rel="noopener noreferrer"
                className="flex items-center justify-between p-3 rounded-xl bg-white/5 hover:bg-white/10 transition"
              >
                <div>
                  <p className="text-sm text-white font-medium">{r.name}</p>
                  <p className="text-xs text-slate-400">
                    {r.total_reviews} reviews
                  </p>
                </div>

                <div className="text-red-400 font-semibold">
                  {r.rating.toFixed(1)}
                </div>
              </a>
            ))}
          </div>
        </div>
      </div>
    </div>
  );
}