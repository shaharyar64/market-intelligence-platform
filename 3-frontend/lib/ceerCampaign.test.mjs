import test from "node:test";
import assert from "node:assert/strict";
import { themeComparison, activitySeries } from "./ceerCampaignAnalysis.ts";

test("theme shares aggregate subthemes without counting the denominator twice", () => {
  const row = (period, theme, items, total) => ({
    comparison_period: period,
    theme,
    sub_theme: "detail",
    items,
    period_items: total,
    share_pct: 0,
  });
  const result = themeComparison(
    [
      row("before", "Design", 10, 100),
      row("after", "Design", 10, 50),
      row("after", "Design", 5, 50),
      row("after", "Price", 20, 50),
    ],
    [row("after", "Design", 5, 10)],
  );
  assert.deepEqual(
    result.find((r) => r.theme === "Design"),
    { theme: "Design", before: 10, after: 30, posts: 50, shift: 20, gap: -20 },
  );
  assert.deepEqual(
    result.find((r) => r.theme === "Price"),
    { theme: "Price", before: 0, after: 40, posts: 0, shift: 40, gap: 40 },
  );
  assert.deepEqual(themeComparison([], []), []);
  assert.equal(themeComparison([row("after", "Empty", 0, 0)], [])[0].after, 0);
});

test("publishing series combines platforms and orders recorded dates", () => {
  assert.deepEqual(
    activitySeries(
      [
        {
          date: "2026-09-22",
          platform: "twitter",
          posts: 1,
          views: 40,
          engagements: 5,
        },
        {
          date: "2026-09-21",
          platform: "instagram",
          posts: 2,
          views: 0,
          engagements: 10,
        },
        {
          date: "2026-09-21",
          platform: "twitter",
          posts: 3,
          views: 100,
          engagements: 20,
        },
      ],
      "posts",
    ),
    [
      { date: "2026-09-21", instagram: 2, linkedin: 0, tiktok: 0, twitter: 3 },
      { date: "2026-09-22", instagram: 0, linkedin: 0, tiktok: 0, twitter: 1 },
    ],
  );
});
