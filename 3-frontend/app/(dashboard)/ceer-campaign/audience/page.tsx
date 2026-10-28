"use client";

import { useState } from "react";
import Image from "next/image";
import {
  Bar,
  BarChart,
  CartesianGrid,
  Legend,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import { getAllAudienceThemes, getCommentsFeed, getCommunityPulse, getThemes } from "@/lib/ceerCampaign";
import { themeComparison } from "@/lib/ceerCampaignAnalysis";
import { useAsyncResource } from "@/lib/useAsyncResource";
import {
  axis,
  CampaignShell,
  Chart,
  compact,
  Load,
  MoreLink,
  Note,
  number,
  Panel,
  platform,
  s,
  tooltip,
} from "../shared";

const themeGuide = [
  ["Brand & Market Perception", "Overall opinions about CEER: praise, trust, quality, competitors, and purchase intent."],
  ["Ownership & Commercial Access", "Price, finance, availability, delivery, trims, warranty, and servicing."],
  ["Exterior Design & Product Form", "Vehicle styling, shape, lights, colours, wheels, doors, and exterior features."],
  ["Saudi Brand & Industrial Impact", "Saudi identity, Vision 2030, local manufacturing, jobs, partnerships, and economic impact."],
  ["Launch & Brand Narrative", "Teasers, reveal events, launch messaging, product roadmap, and CEER’s brand story."],
  ["Cabin & Passenger Experience", "Interior materials, comfort, space, climate, privacy, visibility, and lifestyle use."],
  ["Electric Capability & Regional Readiness", "Battery, range, charging, energy systems, and suitability for Saudi weather."],
  ["Digital Technology & Safety", "Screens, connectivity, apps, smart features, driver assistance, and safety technology."],
] as const;

export default function CampaignAudience() {
  const [selectedTheme, setSelectedTheme] = useState<string>(themeGuide[0][0]);
  const [commentView, setCommentView] = useState<"top" | "all">("top");
  const themes = useAsyncResource(getAllAudienceThemes, []);
  const messaging = useAsyncResource((signal) => getThemes("post", signal), []);
  const community = useAsyncResource(getCommunityPulse, []);
  const comments = useAsyncResource((signal) => getCommentsFeed(commentView, signal), [commentView]);
  const availableThemes = new Set(
    (themes.data ?? [])
      .map((row) => row.theme),
  );
  const orderedThemeOptions = [
    ...themeGuide
      .map(([theme]) => theme)
      .filter((theme) => availableThemes.has(theme)),
    ...[...availableThemes]
      .filter((theme) => !themeGuide.some(([orderedTheme]) => orderedTheme === theme))
      .sort(),
  ];

  return (
    <CampaignShell
      title="Audience comments"
      description="What people discussed around the EXOBOT launch."
    >
      <section className={s.section}>
        <Panel
          title="Theme analysis"
          description="Main topics across all collected audience comments, including YouTube."
        >
          <Load resource={themes}>
            {(rows) => {
              const totals = new Map<string, number>();
              for (const row of rows) totals.set(row.theme, (totals.get(row.theme) ?? 0) + row.items);
              const total = rows[0]?.total_items ?? 0;
              const data = [...totals.entries()]
                .map(([name, items]) => ({ name, items, share: total ? (items / total) * 100 : 0 }))
                .sort((a, b) => b.items - a.items || a.name.localeCompare(b.name));
              return (
                <Chart label="Audience theme share across all collected comments">
                  <ResponsiveContainer width="100%" height="100%">
                    <BarChart data={data} layout="vertical" margin={{ left: 0, right: 24 }}>
                      <CartesianGrid horizontal={false} stroke="var(--ceer-line)" strokeDasharray="3 4" />
                      <XAxis {...axis} type="number" unit="%" />
                      <YAxis
                        {...axis}
                        type="category"
                        dataKey="name"
                        width={180}
                        tick={{ fill: "var(--ceer-muted)", fontSize: 10 }}
                      />
                      <Tooltip
                        contentStyle={tooltip}
                        formatter={(value) => [`${number(Number(value))}%`, "Share of comments"]}
                      />
                      <Bar dataKey="share" name="Share of comments" fill="#138577" radius={[0, 4, 4, 0]} />
                    </BarChart>
                  </ResponsiveContainer>
                </Chart>
              );
            }}
          </Load>
        </Panel>
      </section>

      <section className={s.section}>
        <Panel
          title="Subtheme analysis"
          description="Choose a theme to see the specific topics discussed across all collected comments."
          action={
            <label className={s.filterControl}>
              Theme
              <select
                className={s.select}
                value={selectedTheme}
                onChange={(event) => setSelectedTheme(event.target.value)}
              >
                {orderedThemeOptions.map((theme) => (
                  <option key={theme} value={theme}>{theme}</option>
                ))}
              </select>
            </label>
          }
        >
          <Load resource={themes}>
            {(rows) => {
              const data = rows
                .filter((row) => row.theme === selectedTheme)
                .map((row) => ({
                  name: row.sub_theme,
                  theme: row.theme,
                  items: row.items,
                  share: row.share_pct,
                }));
              return data.length ? (
                <Chart label="Audience subtheme share across all collected comments">
                  <ResponsiveContainer width="100%" height="100%">
                    <BarChart data={data} layout="vertical" margin={{ left: 0, right: 24 }}>
                      <CartesianGrid horizontal={false} stroke="var(--ceer-line)" strokeDasharray="3 4" />
                      <XAxis {...axis} type="number" unit="%" />
                      <YAxis
                        {...axis}
                        type="category"
                        dataKey="name"
                        width={190}
                        interval={0}
                        tick={{ fill: "var(--ceer-muted)", fontSize: 10 }}
                      />
                      <Tooltip
                        contentStyle={tooltip}
                        formatter={(value, _name, item) => [
                          `${number(Number(value))}% (${number(item.payload.items)} comments)`,
                          item.payload.theme,
                        ]}
                      />
                      <Bar dataKey="share" name="Share of comments" fill="#5879bb" radius={[0, 4, 4, 0]} />
                    </BarChart>
                  </ResponsiveContainer>
                </Chart>
              ) : <p className={s.empty}>No subthemes available for this selection.</p>;
            }}
          </Load>
        </Panel>
      </section>

      <div className={s.equalGrid}>
        <Panel
          title="Brand posts and audience comments"
          description="Compare CEER's after-launch posts with all collected audience comments, including YouTube."
        >
          <Load resource={themes}>
            {(audience) => (
              <Load resource={messaging}>
                {(posts) => {
                  const comparison = themeComparison(
                    audience.map((row) => ({ ...row, comparison_period: "after" as const, period_items: row.total_items })),
                    posts,
                  );
                  const gap = comparison
                    .filter(
                      (row) =>
                        row.gap > 0 &&
                        !/other|limited|unrelated|spam/i.test(row.theme),
                    )
                    .sort((a, b) => b.gap - a.gap)[0];
                  return (
                    <>
                      <Chart label="Theme share in after-launch posts versus all collected audience comments">
                        <ResponsiveContainer width="100%" height="100%">
                          <BarChart
                            data={comparison}
                            layout="vertical"
                            margin={{ left: 0, right: 8 }}
                          >
                            <CartesianGrid
                              horizontal={false}
                              stroke="var(--ceer-line)"
                              strokeDasharray="3 4"
                            />
                            <XAxis {...axis} type="number" unit="%" />
                            <YAxis
                              {...axis}
                              type="category"
                              dataKey="theme"
                              width={125}
                              tick={{ fill: "var(--ceer-muted)", fontSize: 10 }}
                            />
                            <Tooltip
                              contentStyle={tooltip}
                              formatter={(value) => `${number(Number(value))}%`}
                            />
                            <Legend />
                            <Bar
                              dataKey="posts"
                              name="Brand posts"
                              fill="#a8b8c4"
                              radius={[0, 3, 3, 0]}
                            />
                            <Bar
                              dataKey="after"
                              name="Audience comments"
                              fill="#138577"
                              radius={[0, 3, 3, 0]}
                            />
                          </BarChart>
                        </ResponsiveContainer>
                      </Chart>
                      {gap ? (
                        <div className={s.summary}>
                          <strong>{gap.theme}</strong> receives{" "}
                          {number(gap.gap)} percentage points more attention in
                          comments than in brand posts. A topic to investigate,
                          not evidence of unmet demand.
                        </div>
                      ) : null}
                    </>
                  );
                }}
              </Load>
            )}
          </Load>
        </Panel>
        <Panel
          title="Collected comments"
          description="Comments available by channel."
        >
          <Load resource={community}>
            {(rows) => (
              <>
                <Chart label="Collected comment counts by platform">
                  <ResponsiveContainer width="100%" height="100%">
                    <BarChart
                      data={rows.map((row) => ({
                        ...row,
                        channel: platform(row.platform),
                      }))}
                      margin={{ left: 0, right: 4 }}
                    >
                      <CartesianGrid
                        vertical={false}
                        stroke="var(--ceer-line)"
                        strokeDasharray="3 4"
                      />
                      <XAxis {...axis} dataKey="channel" />
                      <YAxis {...axis} width={40} tickFormatter={compact} />
                      <Tooltip
                        contentStyle={tooltip}
                        formatter={(value) => number(Number(value))}
                      />
                      <Bar
                        dataKey="comments"
                        name="Collected comments"
                        fill="#5879bb"
                        radius={[5, 5, 0, 0]}
                      />
                    </BarChart>
                  </ResponsiveContainer>
                </Chart>
                <Note>
                  {number(rows.reduce((sum, row) => sum + row.comments, 0))}{" "}
                  comments collected. This includes {number(rows.find((row) => row.platform === "youtube")?.comments ?? 0)} undated
                  YouTube comments in the audience theme charts above, but not
                  in time-based launch comparisons.
                </Note>
              </>
            )}
          </Load>
        </Panel>
      </div>

      <section className={s.section}>
        <Panel
          title={commentView === "top" ? "Top comments" : "All comments"}
          description={commentView === "top" ? "Comments with the most recorded likes." : "All collected comments across social channels and YouTube."}
          action={<div className={s.searchTabs}>
            {(["top", "all"] as const).map((view) => <button key={view} type="button" className={commentView === view ? s.searchTabActive : s.searchTab} onClick={() => setCommentView(view)}>{view === "top" ? "Top comments" : "All comments"}</button>)}
          </div>}
        >
          <Load resource={comments}>
            {({ items, total }) => <>
              <div className={s.tableWrap}>
                <table className={s.table}>
                  <thead><tr><th>Channel</th><th>Comment</th><th>Theme</th><th>Likes</th></tr></thead>
                  <tbody>{items.map((comment) => <tr key={`${comment.platform}-${comment.comment_id}`}>
                    <td>{platform(comment.platform)}</td>
                    <td dir="auto" title={comment.comment_text}>{comment.comment_text || "No text captured"}</td>
                    <td>{comment.sub_theme || "Not classified"}</td>
                    <td>{number(comment.likes)}</td>
                  </tr>)}</tbody>
                </table>
              </div>
              <Note>Showing {items.length} of {number(total)} comments.</Note>
            </>}
          </Load>
        </Panel>
      </section>

      <section className={s.section}>
        <Panel
          title="Competitor mentions"
          description="See other car brands people named or compared with CEER in collected comments."
          action={<MoreLink href="/ceer-campaign/competitors">Explore competitor mentions</MoreLink>}
        >
          <p className={s.note}>Brand mentions are checked against the original comment text. Direct comparisons are shown separately from ordinary mentions.</p>
        </Panel>
      </section>

      <aside className={s.audienceVisual} aria-label="Vehicle design context">
        <div className={s.audienceVisualCopy}>
          <span>Visual context</span>
          <h2>Design became part of the conversation.</h2>
          <p>
            Audience themes show what people discussed around the reveal,
            including the vehicle, ownership and experience.
          </p>
        </div>
        <Image
          src="/ceer/exobot-sedan-portrait.webp"
          alt="Side profile of the CEER EXOBOT Sedan in a dramatic studio"
          fill
          sizes="(max-width: 700px) 100vw, 46vw"
        />
      </aside>

      <section className={s.section}>
        <Panel
          title="What the themes mean"
          description="A simple guide to the topics used to group audience comments."
        >
          <div className={s.themeGuide}>
            {themeGuide.map(([theme, explanation]) => (
              <div key={theme}>
                <strong>{theme}</strong>
                <p>{explanation}</p>
              </div>
            ))}
          </div>
        </Panel>
      </section>

    </CampaignShell>
  );
}
