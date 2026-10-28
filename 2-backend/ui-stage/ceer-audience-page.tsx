"use client";

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
import { getCommunityPulse, getSentiment, getThemes } from "@/lib/ceerCampaign";
import { themeComparison } from "@/lib/ceerCampaignAnalysis";
import { useAsyncResource } from "@/lib/useAsyncResource";
import {
  axis,
  CampaignShell,
  Chart,
  compact,
  delta,
  Load,
  Note,
  number,
  Panel,
  platform,
  s,
  tooltip,
} from "../shared";

const sentimentColors = {
  positive: "#138577",
  neutral: "#6a7e91",
  negative: "#b65357",
};

export default function CampaignAudience() {
  const sentiment = useAsyncResource(getSentiment, []);
  const themes = useAsyncResource(
    (signal) => getThemes("audience_comment", signal),
    [],
  );
  const messaging = useAsyncResource((signal) => getThemes("post", signal), []);
  const community = useAsyncResource(getCommunityPulse, []);

  return (
    <CampaignShell
      title="The conversation behind the numbers."
      description="A directional view of collected discussion and the relationship between published themes and audience attention."
    >
      <div className={s.equalGrid} style={{ marginTop: 0 }}>
        <Panel
          title="What the collected sample indicates"
          description="Sentiment among usable collected comments in the pre-reveal and reveal windows."
        >
          <Load resource={sentiment}>
            {(rows) => {
              const positiveBefore = rows.find(
                (row) =>
                  row.comparison_period === "before" &&
                  row.sentiment === "positive",
              );
              const positiveAfter = rows.find(
                (row) =>
                  row.comparison_period === "after" &&
                  row.sentiment === "positive",
              );
              return (
                <>
                  {(["before", "after"] as const).map((period) => {
                    const subset = rows.filter(
                      (row) => row.comparison_period === period,
                    );
                    return (
                      <div key={period} className={s.sentimentRow}>
                        <div className={s.rowHeader}>
                          <strong>
                            {period === "after"
                              ? "Reveal window"
                              : "Pre-reveal window"}
                          </strong>
                          <small>
                            {subset.length
                              ? `${number(subset[0].usable_comments)} usable comments`
                              : "No records"}
                          </small>
                        </div>
                        <div className={s.sentimentBar}>
                          {(["positive", "neutral", "negative"] as const).map(
                            (key) => {
                              const row = subset.find(
                                (item) => item.sentiment === key,
                              );
                              return row ? (
                                <span
                                  key={key}
                                  style={{
                                    width: `${row.share_pct}%`,
                                    background: sentimentColors[key],
                                  }}
                                  title={`${key}: ${row.share_pct}% (${number(row.comments)} comments)`}
                                  aria-label={`${key}: ${row.share_pct}% (${number(row.comments)} comments)`}
                                >
                                  {row.share_pct >= 5
                                    ? `${number(row.share_pct)}%`
                                    : ""}
                                </span>
                              ) : null;
                            },
                          )}
                        </div>
                      </div>
                    );
                  })}
                  <div className={s.legend}>
                    {Object.entries(sentimentColors).map(([key, color]) => (
                      <span key={key}>
                        <i className={s.dot} style={{ background: color }} />
                        {platform(key)}
                      </span>
                    ))}
                  </div>
                  {positiveBefore && positiveAfter ? (
                    <div className={s.summary}>
                      <strong>
                        {number(positiveAfter.share_pct)}% positive in the
                        reveal window.
                      </strong>{" "}
                      A shift of{" "}
                      {delta(
                        positiveAfter.share_pct - positiveBefore.share_pct,
                        " percentage points",
                      )}{" "}
                      from the pre-reveal sample. Sample sizes differ; this
                      is not a representative opinion poll.
                    </div>
                  ) : null}
                </>
              );
            }}
          </Load>
        </Panel>
        <Panel
          title="Which topics are most present?"
          description="Audience theme share in the collected sample. The marker shows the pre-reveal share."
        >
          <Load resource={themes}>
            {(rows) => (
              <>
                <div className={s.themeRows}>
                  {themeComparison(rows, [])
                    .slice(0, 8)
                    .map((row) => (
                      <div key={row.theme}>
                        <div className={s.themeLabel}>
                          <span>{row.theme}</span>
                          <span>
                            {number(row.after)}%{" "}
                            <span
                              className={
                                row.shift < 0 ? s.negative : s.positive
                              }
                            >
                              ({delta(row.shift, " pp")})
                            </span>
                          </span>
                        </div>
                        <div
                          className={s.themeTrack}
                          title={`Before ${number(row.before)}%; after ${number(row.after)}%`}
                        >
                          <span style={{ width: `${row.after}%` }} />
                          <i style={{ left: `${row.before}%` }} />
                        </div>
                      </div>
                    ))}
                </div>
                <div className={s.legend}>
                  <span>
                    <i
                      className={s.dot}
                      style={{ background: "var(--ceer-accent)" }}
                    />
                    Reveal window
                  </span>
                  <span>
                    <i className={s.dot} style={{ background: "#a65a88" }} />
                    Pre-reveal window
                  </span>
                </div>
                <Note>
                  Subthemes are grouped under their parent theme. Changes are
                  percentage points, not percentage growth.
                </Note>
              </>
            )}
          </Load>
        </Panel>
      </div>

      <div className={s.equalGrid}>
        <Panel
          title="Brand message vs. audience attention"
          description="Reveal-window theme share in published posts and collected comments."
        >
          <Load resource={themes}>
            {(audience) => (
              <Load resource={messaging}>
                {(posts) => {
                  const comparison = themeComparison(audience, posts);
                  const gap = comparison
                    .filter(
                      (row) =>
                        row.gap > 0 &&
                        !/other|limited|unrelated|spam/i.test(row.theme),
                    )
                    .sort((a, b) => b.gap - a.gap)[0];
                  return (
                    <>
                      <Chart label="After-launch theme share in posts versus audience comments">
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
          title="The comment sample"
          description="Collected comments by channel across the captured launch dataset."
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
                  comments collected. Collection coverage differs by channel.
                  This sample is larger than the usable, launch-window subset
                  shown in sentiment.
                </Note>
              </>
            )}
          </Load>
        </Panel>
      </div>

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

      <div className={s.section}>
        <Panel
          title="Topics in collected discussion"
          description="Leading audience subthemes in the reveal window, with pre-reveal context."
        >
          <Load resource={themes}>
            {(rows) => (
              <div className={s.tableWrap}>
                <table className={s.table}>
                  <thead>
                    <tr>
                      <th>Topic</th>
                      <th>Theme</th>
                      <th>Comments in reveal window</th>
                      <th>Share pre-reveal</th>
                      <th>Share reveal window</th>
                      <th>Shift</th>
                    </tr>
                  </thead>
                  <tbody>
                    {rows
                      .filter((row) => row.comparison_period === "after")
                      .sort((a, b) => b.items - a.items)
                      .slice(0, 12)
                      .map((row) => {
                        const before =
                          rows.find(
                            (item) =>
                              item.comparison_period === "before" &&
                              item.theme === row.theme &&
                              item.sub_theme === row.sub_theme,
                          )?.share_pct ?? 0;
                        return (
                          <tr key={`${row.theme}-${row.sub_theme}`}>
                            <td>{row.sub_theme}</td>
                            <td>{row.theme}</td>
                            <td>{number(row.items)}</td>
                            <td>{number(before)}%</td>
                            <td>{number(row.share_pct)}%</td>
                            <td
                              className={
                                row.share_pct < before ? s.negative : s.positive
                              }
                            >
                              {delta(row.share_pct - before, " pp")}
                            </td>
                          </tr>
                        );
                      })}
                  </tbody>
                </table>
              </div>
            )}
          </Load>
        </Panel>
      </div>
    </CampaignShell>
  );
}
