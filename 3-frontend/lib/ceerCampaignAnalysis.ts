import type { ActivityDay, LaunchTheme, Theme } from "./ceerCampaign";
import type { SearchInterest, SearchRegion } from "./ceerCampaign";

const saudiHascToIso: Record<string, string> = {
  "SA.AS": "SA-14",
  "SA.BA": "SA-11",
  "SA.HS": "SA-08",
  "SA.JF": "SA-12",
  "SA.MD": "SA-03",
  "SA.QS": "SA-05",
  "SA.RI": "SA-01",
  "SA.SH": "SA-04",
  "SA.HA": "SA-06",
  "SA.JZ": "SA-09",
  "SA.MK": "SA-02",
  "SA.NJ": "SA-10",
  "SA.TB": "SA-07",
};

export function saudiProvinceCode(properties?: Record<string, unknown>) {
  const iso = String(properties?.ISO_1 ?? "").toUpperCase();
  if (/^SA-\d+$/.test(iso)) return iso;
  return saudiHascToIso[String(properties?.HASC_1 ?? "").toUpperCase()] ?? "";
}

export function searchInterestSeries(rows: SearchInterest[]) {
  const series = new Map<
    string,
    {
      total: number;
      count: number;
      values: Map<string, { total: number; count: number }>;
    }
  >();
  for (const row of rows) {
    const label = row.country ? `${row.keyword} — ${row.country}` : row.keyword;
    const entry = series.get(label) ?? {
      total: 0,
      count: 0,
      values: new Map(),
    };
    const value = entry.values.get(row.date) ?? { total: 0, count: 0 };
    value.total += row.interest;
    value.count += 1;
    entry.total += row.interest;
    entry.count += 1;
    entry.values.set(row.date, value);
    series.set(label, entry);
  }
  const keys = [...series.entries()]
    .sort(([, a], [, b]) => b.total / b.count - a.total / a.count)
    .slice(0, 5)
    .map(([label]) => label);
  const dates = [...new Set(rows.map((row) => row.date))].sort();
  return {
    keys,
    data: dates.map((date) => ({
      date,
      ...Object.fromEntries(
        keys.flatMap((key) => {
          const value = series.get(key)?.values.get(date);
          return value ? [[key, value.total / value.count]] : [];
        }),
      ),
    })),
  };
}

export function regionalSearchScores(rows: SearchRegion[]) {
  const regions = new Map<
    string,
    { total: number; count: number; name: string; keyword: string }
  >();
  for (const row of rows) {
    if (!row.geo_code || !Number.isFinite(row.score)) continue;
    const code = row.geo_code.toUpperCase();
    const region = regions.get(code) ?? {
      total: 0,
      count: 0,
      name: row.geo_name,
      keyword: row.keyword,
    };
    region.total += row.score;
    region.count += 1;
    region.name = row.geo_name || region.name;
    region.keyword = row.keyword || region.keyword;
    regions.set(code, region);
  }
  return new Map(
    [...regions.entries()].map(([code, region]) => [
      code,
      {
        score: region.total / region.count,
        name: region.name,
        keyword: region.keyword,
      },
    ]),
  );
}

export function themeComparison(audience: Theme[], posts: Theme[]) {
  const themes = [...new Set([...audience, ...posts].map((row) => row.theme))];
  function share(rows: Theme[], theme: string, period: "before" | "after") {
    const window = rows.filter((row) => row.comparison_period === period);
    const total = Math.max(0, ...window.map((row) => row.period_items));
    return total
      ? (window
          .filter((row) => row.theme === theme)
          .reduce((sum, row) => sum + row.items, 0) /
          total) *
          100
      : 0;
  }
  return themes
    .map((theme) => {
      const before = share(audience, theme, "before");
      const after = share(audience, theme, "after");
      const postShare = share(posts, theme, "after");
      return {
        theme,
        before,
        after,
        posts: postShare,
        shift: after - before,
        gap: after - postShare,
      };
    })
    .sort((a, b) => b.after - a.after);
}

export function launchThemeMatrix(rows: LaunchTheme[]) {
  const periods: LaunchTheme["period"][] = ["before", "launch_day", "after"];
  const themes = [...new Set(rows.map((row) => row.theme))];
  return themes
    .map((theme) => ({
      label: theme,
      values: periods.map(
        (period) => rows.find((row) => row.theme === theme && row.period === period)?.share_pct ?? 0,
      ),
    }))
    .sort((a, b) => Math.max(...b.values) - Math.max(...a.values));
}

export function activitySeries(
  days: ActivityDay[],
  metric: "posts" | "views" | "engagements",
) {
  const dates = new Map<
    string,
    {
      date: string;
      instagram: number;
      linkedin: number;
      tiktok: number;
      twitter: number;
    }
  >();
  for (const row of days) {
    const point = dates.get(row.date) ?? {
      date: row.date,
      instagram: 0,
      linkedin: 0,
      tiktok: 0,
      twitter: 0,
    };
    if (
      row.platform === "instagram" ||
      row.platform === "linkedin" ||
      row.platform === "tiktok" ||
      row.platform === "twitter"
    )
      point[row.platform] += row[metric];
    dates.set(row.date, point);
  }
  return [...dates.values()].sort((a, b) => a.date.localeCompare(b.date));
}

export function dailyActivitySeries(
  days: ActivityDay[],
  metric: "posts" | "views" | "engagements",
) {
  const recorded = activitySeries(days, metric);
  if (!recorded.length) return [];
  const byDate = new Map(recorded.map((row) => [row.date, row]));
  const result = [];
  const cursor = new Date(`${recorded[0].date}T00:00:00Z`);
  const end = recorded[recorded.length - 1].date;
  for (
    ;
    cursor.toISOString().slice(0, 10) <= end;
    cursor.setUTCDate(cursor.getUTCDate() + 1)
  ) {
    const date = cursor.toISOString().slice(0, 10);
    const row = byDate.get(date) ?? {
      date,
      instagram: 0,
      linkedin: 0,
      tiktok: 0,
      twitter: 0,
    };
    result.push({
      ...row,
      total: row.instagram + row.linkedin + row.tiktok + row.twitter,
    });
  }
  return result;
}

export function themeMatrix(audience: Theme[], posts: Theme[]) {
  const comparison = themeComparison(audience, posts);
  const postComparison = new Map(
    themeComparison(posts, []).map((row) => [row.theme, row]),
  );
  const hasWindow = (rows: Theme[], period: "before" | "after") =>
    rows.some(
      (row) => row.comparison_period === period && row.period_items > 0,
    );
  return comparison.map((row) => ({
    label: row.theme,
    values: [
      hasWindow(audience, "before") ? row.before : null,
      hasWindow(audience, "after") ? row.after : null,
      hasWindow(posts, "before")
        ? (postComparison.get(row.theme)?.before ?? 0)
        : null,
      hasWindow(posts, "after")
        ? (postComparison.get(row.theme)?.after ?? 0)
        : null,
    ],
  }));
}

export function subthemeSeries(
  rows: Theme[],
  period: "before" | "after",
  theme: string,
) {
  const window = rows.filter((row) => row.comparison_period === period);
  const denominator = Math.max(0, ...window.map((row) => row.period_items));
  return window
    .filter((row) => theme === "all" || row.theme === theme)
    .map((row) => ({
      name: row.sub_theme,
      theme: row.theme,
      items: row.items,
      share: denominator ? (row.items / denominator) * 100 : 0,
    }))
    .sort((a, b) => b.items - a.items)
    .slice(0, 12);
}
