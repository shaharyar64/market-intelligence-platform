import test from "node:test";
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import * as analysis from "./ceerCampaignAnalysis.ts";

test("daily engagement series fills gaps and preserves platform totals", () => {
  const rows = [
    {
      date: "2026-09-21",
      platform: "twitter",
      posts: 2,
      views: 100,
      engagements: 20,
    },
    {
      date: "2026-09-21",
      platform: "instagram",
      posts: 1,
      views: 0,
      engagements: 5,
    },
    {
      date: "2026-09-23",
      platform: "twitter",
      posts: 1,
      views: 30,
      engagements: 7,
    },
  ];
  assert.deepEqual(analysis.dailyActivitySeries(rows, "engagements"), [
    {
      date: "2026-09-21",
      instagram: 5,
      linkedin: 0,
      tiktok: 0,
      twitter: 20,
      total: 25,
    },
    {
      date: "2026-09-22",
      instagram: 0,
      linkedin: 0,
      tiktok: 0,
      twitter: 0,
      total: 0,
    },
    {
      date: "2026-09-23",
      instagram: 0,
      linkedin: 0,
      tiktok: 0,
      twitter: 7,
      total: 7,
    },
  ]);
  assert.equal(analysis.dailyActivitySeries(rows, "posts")[0].total, 3);
  assert.deepEqual(analysis.dailyActivitySeries([], "posts"), []);
});

test("theme heatmap distinguishes missing windows from zero share", () => {
  const rows = [
    {
      comparison_period: "after",
      theme: "Design",
      sub_theme: "Exterior",
      items: 20,
      period_items: 100,
      share_pct: 20,
    },
  ];
  assert.deepEqual(analysis.themeMatrix(rows, []), [
    { label: "Design", values: [null, 20, null, null] },
  ]);
  assert.deepEqual(analysis.themeMatrix([], []), []);
});

test("launch theme matrix includes a separately normalized launch-day column", () => {
  const rows = [
    { period: "before", theme: "Launch", items: 10, period_items: 10, share_pct: 100 },
    { period: "launch_day", theme: "Launch", items: 8, period_items: 10, share_pct: 80 },
    { period: "launch_day", theme: "Design", items: 2, period_items: 10, share_pct: 20 },
    { period: "after", theme: "Design", items: 5, period_items: 5, share_pct: 100 },
  ];

  assert.deepEqual(analysis.launchThemeMatrix(rows), [
    { label: "Launch", values: [100, 80, 0] },
    { label: "Design", values: [0, 20, 100] },
  ]);
});

test("subtheme filter preserves whole-window denominator and excludes other windows", () => {
  const rows = [
    {
      comparison_period: "after",
      theme: "Design",
      sub_theme: "Exterior",
      items: 20,
      period_items: 100,
      share_pct: 20,
    },
    {
      comparison_period: "after",
      theme: "Design",
      sub_theme: "Interior",
      items: 10,
      period_items: 100,
      share_pct: 10,
    },
    {
      comparison_period: "before",
      theme: "Design",
      sub_theme: "Exterior",
      items: 90,
      period_items: 100,
      share_pct: 90,
    },
    {
      comparison_period: "after",
      theme: "Purchase",
      sub_theme: "Price",
      items: 70,
      period_items: 100,
      share_pct: 70,
    },
  ];
  assert.deepEqual(
    analysis
      .subthemeSeries(rows, "after", "Design")
      .map((row) => [row.name, row.share]),
    [
      ["Exterior", 20],
      ["Interior", 10],
    ],
  );
  assert.deepEqual(analysis.subthemeSeries(rows, "after", "Unknown"), []);
});

test("search-interest series keeps the five strongest readable terms", () => {
  const result = analysis.searchInterestSeries([
    { date: "2026-09-21", keyword: "EXOBOT", country: "SA", interest: 80 },
    { date: "2026-09-22", keyword: "EXOBOT", country: "SA", interest: 60 },
    { date: "2026-09-21", keyword: "CEER", country: "SA", interest: 40 },
    { date: "2026-09-22", keyword: "CEER", country: "SA", interest: 50 },
    { date: "2026-09-21", keyword: "Duplicate", country: "SA", interest: 10 },
    { date: "2026-09-21", keyword: "Duplicate", country: "SA", interest: 30 },
    { date: "2026-09-21", keyword: "Third", country: "SA", interest: 20 },
    { date: "2026-09-21", keyword: "Fourth", country: "SA", interest: 15 },
    { date: "2026-09-21", keyword: "Fifth", country: "SA", interest: 10 },
    { date: "2026-09-21", keyword: "Brand", country: "SA", interest: 1 },
  ]);

  assert.deepEqual(result.keys, [
    "EXOBOT — SA",
    "CEER — SA",
    "Duplicate — SA",
    "Third — SA",
    "Fourth — SA",
  ]);
  assert.deepEqual(result.data, [
    {
      date: "2026-09-21",
      "EXOBOT — SA": 80,
      "CEER — SA": 40,
      "Duplicate — SA": 20,
      "Third — SA": 20,
      "Fourth — SA": 15,
    },
    { date: "2026-09-22", "EXOBOT — SA": 60, "CEER — SA": 50 },
  ]);
});

test("regional search scores average repeated province snapshots", () => {
  assert.deepEqual(
    analysis.regionalSearchScores([
      {
        keyword: "ceer",
        geo_code: "SA-01",
        geo_name: "Riyadh",
        country: "SA",
        score: 100,
      },
      {
        keyword: "ceer",
        geo_code: "sa-01",
        geo_name: "Riyadh Province",
        country: "SA",
        score: 80,
      },
      {
        keyword: "ceer",
        geo_code: "SA-02",
        geo_name: "Makkah Province",
        country: "SA",
        score: 60,
      },
    ]),
    new Map([
      ["SA-01", { score: 90, name: "Riyadh Province", keyword: "ceer" }],
      ["SA-02", { score: 60, name: "Makkah Province", keyword: "ceer" }],
    ]),
  );
});

test("Saudi GeoJSON HASC fallbacks resolve every province missing an ISO code", () => {
  assert.deepEqual(
    ["SA.MD", "SA.QS", "SA.SH", "SA.HA", "SA.JZ", "SA.MK"].map((HASC_1) =>
      analysis.saudiProvinceCode({ ISO_1: "NA", HASC_1 }),
    ),
    ["SA-03", "SA-05", "SA-04", "SA-06", "SA-09", "SA-02"],
  );
});

test("search-interest panels are stacked and the province map stays focused", () => {
  const page = readFileSync(
    new URL("../app/(dashboard)/ceer-campaign/page.tsx", import.meta.url),
    "utf8",
  );
  const map = readFileSync(
    new URL("../components/maps/CeerSearchMap.tsx", import.meta.url),
    "utf8",
  );

  assert.match(
    page,
    /<div className=\{s\.section\}>[\s\S]*?<Panel\s+title=\{`\$\{searchLabel\} search interest around the reveal`\}/,
  );
  assert.doesNotMatch(map, /TileLayer/);
  assert.match(map, /zoomControl=\{false\}/);
  assert.match(map, /fitBounds\(/);
  assert.match(map, /const \[map, setMap\] = useState<LeafletMap \| null>\(null\)/);
  assert.match(map, /style=\{\{ height: 540, width: "100%" \}\}/);
});

test("CEER and EXOBOT search tabs request matching line and region data", () => {
  const page = readFileSync(
    new URL("../app/(dashboard)/ceer-campaign/page.tsx", import.meta.url),
    "utf8",
  );
  const client = readFileSync(new URL("./ceerCampaign.ts", import.meta.url), "utf8");

  assert.match(page, /const \[searchKeyword, setSearchKeyword\] = useState<SearchKeyword>\("ceer"\)/);
  assert.match(page, /getSearchInterest\(searchKeyword, signal\)/);
  assert.match(page, /getSearchRegions\(searchKeyword, signal\)/);
  assert.match(page, /\["ceer", "exobot"\]/);
  assert.match(client, /search-interest\?keyword=\$\{encodeURIComponent\(keyword\)\}/);
  assert.match(client, /search-regions\?keyword=\$\{encodeURIComponent\(keyword\)\}/);
});

test("the live launch page renders the CEER and EXOBOT search-trends panels", () => {
  const launchImpact = readFileSync(
    new URL("../app/(dashboard)/ceer-campaign/launch-impact.tsx", import.meta.url),
    "utf8",
  );

  assert.match(launchImpact, /import SearchTrendPanels from "\.\/search-trends"/);
  assert.match(launchImpact, /<SearchTrendPanels\s*\/>/);
});

test("the live launch page renders one all-channel post-theme heatmap", () => {
  const launchImpact = readFileSync(
    new URL("../app/(dashboard)/ceer-campaign/launch-impact.tsx", import.meta.url),
    "utf8",
  );

  assert.match(launchImpact, /getLaunchThemes/);
  assert.match(launchImpact, /launchThemeMatrix\(rows\)/);
  assert.match(launchImpact, /title="All-channel theme mix"/);
  assert.match(launchImpact, />Week before</);
  assert.match(launchImpact, />Launch day</);
  assert.match(launchImpact, />Week after</);
});

test("launch study leads with collected comments and a descriptive total-likes comparison", () => {
  const page = readFileSync(
    new URL("../app/(dashboard)/ceer-campaign/page.tsx", import.meta.url),
    "utf8",
  );
  const shared = readFileSync(
    new URL("../app/(dashboard)/ceer-campaign/shared.tsx", import.meta.url),
    "utf8",
  );

  assert.match(page, /label: "Collected comments",\s*value: kpis\.collected_comments/);
  assert.doesNotMatch(page, /label: "Public comments"/);
  assert.match(page, /const \[measure, setMeasure\] = useState<keyof typeof measures>\("totalLikes"\)/);
  assert.match(page, /title="How response differed across the launch windows"/);
  assert.match(page, /label: "Total likes",\s*before: "total_likes_before",\s*after: "total_likes_after"/);
  assert.match(shared, /DashboardTopbar title="CEER EXOBOT Launch Signal Study"/);
});

test("launch narrative uses an all-channel three-period impact view", () => {
  const page = readFileSync(
    new URL("../app/(dashboard)/ceer-campaign/launch-impact.tsx", import.meta.url),
    "utf8",
  );
  const client = readFileSync(new URL("./ceerCampaign.ts", import.meta.url), "utf8");
  const shared = readFileSync(
    new URL("../app/(dashboard)/ceer-campaign/shared.tsx", import.meta.url),
    "utf8",
  );

  assert.match(page, /getLaunchImpact/);
  assert.match(page, /All-channel engagement around the launch/);
  assert.match(page, /Launch day/);
  assert.match(page, /Engagements = likes \+ shares \+ public comments/);
  assert.match(client, /getJson<LaunchImpactMetric\[\]>\("launch-impact", signal\)/);
  assert.match(shared, /\["\/ceer-campaign", "Launch impact"\]/);
  assert.match(shared, /\["\/ceer-campaign\/content", "Channel analysis"\]/);
  assert.match(shared, /\["\/ceer-campaign\/audience", "Conversation topics"\]/);
});

test("overview distinguishes data coverage from response analysis", () => {
  const page = readFileSync(
    new URL("../app/(dashboard)/ceer-campaign/page.tsx", import.meta.url),
    "utf8",
  );
  const shared = readFileSync(
    new URL("../app/(dashboard)/ceer-campaign/shared.tsx", import.meta.url),
    "utf8",
  );

  assert.match(page, /title="Where reported views came from"/);
  assert.match(page, /View reporting coverage/);
  assert.match(page, /title="Channel data coverage"/);
  assert.match(page, /YouTube/);
  assert.doesNotMatch(shared, /independent|not commissioned/i);
});
