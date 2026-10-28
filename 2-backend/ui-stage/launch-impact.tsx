"use client";

import Image from "next/image";
import {
  Bar,
  BarChart,
  CartesianGrid,
  LabelList,
  Line,
  LineChart,
  ReferenceLine,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import { getActivity, getLaunchImpact, getLaunchThemes, type LaunchTheme } from "@/lib/ceerCampaign";
import { dailyActivitySeries, launchThemeMatrix } from "@/lib/ceerCampaignAnalysis";
import { useAsyncResource } from "@/lib/useAsyncResource";
import SearchTrendPanels from "./search-trends";
import {
  axis,
  CampaignShell,
  Chart,
  compact,
  Load,
  Note,
  number,
  Panel,
  s,
  tooltip,
} from "./shared";

const launchDate = "2026-09-21";
const periodLabels = {
  before: "Week before",
  launch_day: "Launch day",
  after: "Week after",
} as const;

const dateLabel = (date: string) =>
  new Date(`${date}T00:00:00Z`).toLocaleDateString("en", {
    day: "numeric",
    month: "short",
    timeZone: "UTC",
  });

function AllChannelThemeHeatmap({ rows }: { rows: LaunchTheme[] }) {
  const themes = launchThemeMatrix(rows);
  const max = Math.max(1, ...themes.flatMap((theme) => theme.values));

  return (
    <div className={s.tableWrap} tabIndex={0} role="region" aria-label="All-channel theme shares by launch window">
      <table className={s.heatmap}>
        <caption className={s.srOnly}>All-channel theme shares by launch window</caption>
        <thead>
          <tr>
            <th scope="col">Theme</th>
            <th scope="col">Week before</th>
            <th scope="col">Launch day</th>
            <th scope="col">Week after</th>
          </tr>
        </thead>
        <tbody>
          {themes.map((theme) => (
            <tr key={theme.theme}>
              <th scope="row">{theme.label}</th>
              {theme.values.map((share, index) => {
                const strength = Math.log1p(share) / Math.log1p(max);
                return (
                  <td
                    key={index}
                    title={`${theme.label}, ${["week before", "launch day", "week after"][index]}: ${number(share)}%`}
                    style={{ background: `rgba(19, 133, 119, ${0.08 + 0.5 * strength})` }}
                  >
                    {number(share)}%
                  </td>
                );
              })}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

export default function LaunchImpactPage() {
  const impact = useAsyncResource(getLaunchImpact, []);
  const activity = useAsyncResource(getActivity, []);
  const themes = useAsyncResource(getLaunchThemes, []);

  return (
    <CampaignShell
      title="The launch, in focus."
      description="One all-channel read of public response in the week before the EXOBOT reveal, on launch day, and in the week after."
    >
      <section className={s.launchHero} aria-label="EXOBOT launch impact">
        <Image
          src="/ceer/exobot-road.webp"
          alt="CEER EXOBOT Sedan and SUV driving through a desert landscape"
          fill
          sizes="(max-width: 768px) 100vw, 80vw"
          className={s.launchHeroImage}
          priority
        />
        <div className={s.launchHeroShade} />
        <div className={s.launchHeroCopy}>
          <span>21 September 2026</span>
          <h2>A concentrated launch-day response across CEER’s social channels.</h2>
          <p>Engagements combine likes, public comments, and shares. Views remain a separate reach signal.</p>
        </div>
      </section>

      <Load resource={impact}>
        {(rows) => {
          const launch = rows.find((row) => row.period === "launch_day");
          const before = rows.find((row) => row.period === "before");
          const after = rows.find((row) => row.period === "after");
          const launchVsBefore =
            launch && before && before.engagements > 0
              ? ((launch.engagements - before.engagements) / before.engagements) * 100
              : null;
          return (
            <>
              <section className={s.launchWindows} aria-label="All-channel launch periods">
                {rows.map((row) => (
                  <article
                    className={row.period === "launch_day" ? s.launchWindowFocus : s.launchWindow}
                    key={row.period}
                  >
                    <span>{periodLabels[row.period]}</span>
                    <strong title={number(row.engagements)}>{compact(row.engagements)}</strong>
                    <small>{number(row.posts)} published posts · {compact(row.views)} reported views</small>
                  </article>
                ))}
              </section>

              <div className={s.summary}>
                <strong>{launch ? `${compact(launch.engagements)} launch-day engagements` : "Launch-day result unavailable"}.</strong>{" "}
                {launchVsBefore == null
                  ? "Engagements are compared across all captured channels."
                  : `${number(launchVsBefore)}% above the full week-before total, despite being a single day.`}{" "}
                The week after recorded {after ? compact(after.engagements) : "—"} engagements.
              </div>

              <div className={s.equalGrid}>
                <Panel
                  title="All-channel engagement around the launch"
                  description="Likes + public comments + shares for posts published in each period."
                >
                  <Chart label="All-channel engagement before, on, and after launch day">
                    <ResponsiveContainer width="100%" height="100%">
                      <BarChart
                        data={rows.map((row) => ({ period: periodLabels[row.period], engagements: row.engagements }))}
                        margin={{ left: 6, right: 10, top: 18 }}
                      >
                        <CartesianGrid vertical={false} stroke="var(--ceer-line)" strokeDasharray="3 4" />
                        <XAxis {...axis} dataKey="period" />
                        <YAxis {...axis} tickFormatter={compact} width={48} />
                        <Tooltip contentStyle={tooltip} formatter={(value) => number(Number(value))} />
                        <Bar dataKey="engagements" fill="#138577" radius={[7, 7, 0, 0]} animationDuration={800}>
                          <LabelList dataKey="engagements" position="top" formatter={(value) => compact(Number(value))} />
                        </Bar>
                      </BarChart>
                    </ResponsiveContainer>
                  </Chart>
                  <Note>Engagements = likes + shares + public comments. Views are intentionally excluded because they measure exposure rather than an active interaction.</Note>
                </Panel>

                <Panel
                  title="What changed around the reveal"
                  description="Per-post response accounts for differing publishing volume."
                >
                  <div className={s.impactDetails}>
                    {rows.map((row) => (
                      <div key={row.period}>
                        <span>{periodLabels[row.period]}</span>
                        <strong>{row.engagements_per_post == null ? "—" : number(row.engagements_per_post)}</strong>
                        <small>engagements per post</small>
                      </div>
                    ))}
                  </div>
                  <Note>The launch-day concentration is descriptive, not causal attribution. Metrics are the latest captured post totals, not interactions earned on each calendar day.</Note>
                </Panel>
              </div>
            </>
          );
        }}
      </Load>

      <section className={s.section}>
        <Panel
          title="The launch spike in context"
          description="All-channel engagement by publication date. The line animates on load and marks the 21 September reveal."
        >
          <Load resource={activity} empty={(data) => !data.days.length}>
            {(data) => (
              <>
                <Chart label="All-channel engagement trend by publication date">
                  <ResponsiveContainer width="100%" height="100%">
                    <LineChart data={dailyActivitySeries(data.days, "engagements")} margin={{ left: 4, right: 18, top: 12 }}>
                      <CartesianGrid vertical={false} stroke="var(--ceer-line)" strokeDasharray="3 4" />
                      <XAxis {...axis} dataKey="date" tickFormatter={dateLabel} minTickGap={24} />
                      <YAxis {...axis} tickFormatter={compact} width={48} />
                      <Tooltip contentStyle={tooltip} labelFormatter={(value) => dateLabel(String(value))} formatter={(value) => [number(Number(value)), "Engagements"]} />
                      <ReferenceLine x={launchDate} stroke="#b65357" strokeDasharray="4 4" label={{ value: "Launch", fill: "var(--ceer-muted)", fontSize: 11 }} />
                      <Line type="monotone" dataKey="total" name="All channels" stroke="#138577" strokeWidth={3} dot={false} activeDot={{ r: 5 }} animationDuration={900} />
                    </LineChart>
                  </ResponsiveContainer>
                </Chart>
                <Note>Dates with no captured posts display as zero. {data.undated_posts ? `${number(data.undated_posts)} undated posts are excluded.` : "All captured posts have usable dates."}</Note>
              </>
            )}
          </Load>
        </Panel>
      </section>

      <section className={s.section}>
        <Panel
          title="All-channel theme mix"
          description="Theme share of all captured posts by publication window across Instagram, LinkedIn, TikTok, and X."
        >
          <Load resource={themes} empty={(rows) => !rows.length}>
            {(rows) => (
              <>
                <AllChannelThemeHeatmap rows={rows} />
                <Note>Each column totals 100%. Stronger colour marks a larger share of posts in that window.</Note>
              </>
            )}
          </Load>
        </Panel>
      </section>

      <SearchTrendPanels />
    </CampaignShell>
  );
}
