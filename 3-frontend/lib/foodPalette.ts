import type { Quadrant, Source } from "@/lib/foodTrends";

export type TokenFamily = "growth" | "mainstream" | "breakthrough" | "watchlist";

export const graphic = (t: TokenFamily) => `var(--fi-${t})`;

export const CHART_SERIES = [
  "var(--chart-1)", "var(--chart-2)", "var(--chart-3)",
  "var(--chart-4)", "var(--chart-5)", "var(--chart-6)",
] as const;
export const text = (t: TokenFamily) => `var(--fi-${t}-tx)`;
export const soft = (t: TokenFamily) => `var(--fi-${t}-soft)`;
export const softBorder = (t: TokenFamily) => `var(--fi-${t}-soft-bd)`;

export const QUADRANT_META: Record<
  Quadrant,
  { label: string; token: TokenFamily; volGrowth: string }
> = {
  "slow-burner":  { label: "Slow Burner",  token: "growth",       volGrowth: "High volume · High growth" },
  mainstream:     { label: "Mainstream",   token: "mainstream",   volGrowth: "High volume · Low growth" },
  breakthrough:   { label: "Breakthrough", token: "breakthrough", volGrowth: "Low volume · High growth" },
  watchlist:      { label: "Watchlist",    token: "watchlist",    volGrowth: "Low volume · Low growth" },
};

export const QUADRANT_ORDER: Quadrant[] = ["slow-burner", "mainstream", "breakthrough", "watchlist"];

export const TREND_JOURNEY: Quadrant[] = ["watchlist", "breakthrough", "slow-burner", "mainstream"];

export const SOURCE_META: Record<Source, { label: string; token: TokenFamily }> = {
  brand:      { label: "Brands",      token: "growth" },
  influencer: { label: "Influencers", token: "breakthrough" },
  community:  { label: "Consumers",   token: "mainstream" },
};

export const KPI_TOKEN: Record<string, TokenFamily> = {
  trends: "growth",
  watchlist: "watchlist",
  breakthrough: "breakthrough",
  slow: "growth",
  mainstream: "mainstream",
  brands: "watchlist",
};
