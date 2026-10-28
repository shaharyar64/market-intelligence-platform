"use client";

import Image from "next/image";
import {
  Bar,
  BarChart,
  CartesianGrid,
  Cell,
  LabelList,
  Line,
  LineChart,
  ReferenceLine,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import {
  getActivity,
  getCampaignOverview,
  getLaunchImpact,
  getLaunchThemes,
  type LaunchTheme,
} from "@/lib/ceerCampaign";
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
  const overview = useAsyncResource(getCampaignOverview, []);
  const impact = useAsyncResource(getLaunchImpact, []);
  const activity = useAsyncResource(getActivity, []);
  const themes = useAsyncResource(getLaunchThemes, []);

  return (
    <CampaignShell
      title="Launch overview"
      description="Social response before, on, and after the EXOBOT launch."
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
          <h2>Launch-day response across CEER social channels</h2>
          <p>Engagement includes likes, public comments, and shares.</p>
        </div>
      </section>

      <section className={s.section}>
        <Panel
          title="Data used in this analysis"
          description="Matched launch-comparison posts and comments used for audience analysis."
        >
          <Load resource={overview}>
            {({ kpis }) => (
              <Load resource={impact}>
                {(rows) => {
                  const analysisPosts = rows.reduce(
                    (total, row) => total + row.posts,
                    0,
                  );
                  return (
                    <>
                      <div className={s.launchWindows} style={{ gridTemplateColumns: "repeat(2, minmax(0, 1fr))" }}>
                        <article className={s.launchWindow}>
                          <span>Comments used for audience analysis</span>
                          <strong title={number(kpis.collected_comments)}>{compact(kpis.collected_comments)}</strong>
                          <small>All collected comments</small>
                        </article>
                        <article className={s.launchWindowFocus}>
                          <span>Posts used in the launch analysis</span>
                          <strong title={number(analysisPosts)}>{compact(analysisPosts)}</strong>
                          <small>7 days before, launch day, and 7 days after</small>
                        </article>
                      </div>
                      <Note>
                        This keeps the comparison fair by using equal time periods before and after launch.
                      </Note>
                    </>
                  );
                }}
              </Load>
            )}
          </Load>
        </Panel>
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
                  title="Engagement summary"
                  description="Likes, public comments, and shares for posts in each period."
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
                  <Note>Engagement = likes + shares + public comments. Views are shown separately.</Note>
                </Panel>

                <Panel
                  title="Engagement per post"
                  description="Average response per post in each period."
                >
                  <Chart label="Average engagements per post before, on, and after launch day">
                    <ResponsiveContainer width="100%" height="100%">
                      <BarChart
                        data={rows.map((row) => ({
                          period: periodLabels[row.period],
                          engagementsPerPost: row.engagements_per_post,
                        }))}
                        margin={{ left: 6, right: 10, top: 18 }}
                      >
                        <CartesianGrid vertical={false} stroke="var(--ceer-line)" strokeDasharray="3 4" />
                        <XAxis {...axis} dataKey="period" />
                        <YAxis {...axis} tickFormatter={compact} width={48} />
                        <Tooltip
                          contentStyle={tooltip}
                          formatter={(value) => [number(Number(value)), "Engagements per post"]}
                        />
                        <Bar dataKey="engagementsPerPost" radius={[7, 7, 0, 0]} animationDuration={800}>
                          {rows.map((row) => (
                            <Cell
                              key={row.period}
                              fill={row.period === "launch_day" ? "#138577" : "#a8b8c4"}
                            />
                          ))}
                          <LabelList
                            dataKey="engagementsPerPost"
                            position="top"
                            formatter={(value) => number(Number(value))}
                          />
                        </Bar>
                      </BarChart>
                    </ResponsiveContainer>
                  </Chart>
                  <Note>Average engagement per post. Views are not included.</Note>
                </Panel>
              </div>
            </>
          );
        }}
      </Load>

      <section className={s.section}>
        <Panel
          title="Engagement trendline"
          description="All-channel engagement by post date. The marker shows launch day."
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
                <Note>Dates with no captured posts show zero. {data.undated_posts ? `${number(data.undated_posts)} posts without dates are excluded.` : "All posts have usable dates."}</Note>
              </>
            )}
          </Load>
        </Panel>
      </section>

      <section className={s.section}>
        <Panel
          title="Theme analysis"
          description="What CEER posted about before, on, and after launch day."
        >
          <Load resource={themes} empty={(rows) => !rows.length}>
            {(rows) => (
              <>
                <AllChannelThemeHeatmap rows={rows} />
                <Note>Each column totals 100%. Darker colour means more posts on that theme.</Note>
              </>
            )}
          </Load>
        </Panel>
      </section>

      <SearchTrendPanels />
    </CampaignShell>
  );
}
