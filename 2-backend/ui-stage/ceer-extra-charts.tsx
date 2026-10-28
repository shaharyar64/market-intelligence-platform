"use client";

import { useState } from "react";
import {
  Bar,
  BarChart,
  CartesianGrid,
  Legend,
  Line,
  LineChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import type { CampaignActivity, Theme } from "@/lib/ceerCampaign";
import type { Resource } from "@/lib/useAsyncResource";
import {
  dailyActivitySeries,
  subthemeSeries,
  themeMatrix,
} from "@/lib/ceerCampaignAnalysis";
import {
  axis,
  Chart,
  colors,
  compact,
  Load,
  Note,
  number,
  Panel,
  platform,
  s,
  tooltip,
} from "./shared";

const dateLabel = (date: string) =>
  new Date(`${date}T00:00:00Z`).toLocaleDateString("en", {
    day: "numeric",
    month: "short",
    timeZone: "UTC",
  });

function Heatmap({
  columns,
  rows,
  percentage = false,
  label,
}: {
  columns: string[];
  rows: { label: string; values: (number | null)[] }[];
  percentage?: boolean;
  label: string;
}) {
  const max = Math.max(
    1,
    ...rows.flatMap((row) => row.values.map((value) => value ?? 0)),
  );
  return (
    <>
      <div
        className={s.tableWrap}
        tabIndex={0}
        role="region"
        aria-label={`${label}. Scroll horizontally for all columns.`}
      >
        <table className={s.heatmap}>
          <caption className={s.srOnly}>{label}</caption>
          <thead>
            <tr>
              <th scope="col">{percentage ? "Theme" : "Platform"}</th>
              {columns.map((column) => (
                <th scope="col" key={column}>
                  {column}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {rows.map((row) => (
              <tr key={row.label}>
                <th scope="row">{row.label}</th>
                {row.values.map((value, index) => {
                  const strength =
                    value == null || value === 0
                      ? 0
                      : percentage
                        ? value / 100
                        : Math.log1p(value) / Math.log1p(max);
                  return (
                    <td
                      key={columns[index]}
                      title={`${row.label}, ${columns[index]}: ${value == null ? "No data" : number(value) + (percentage ? "%" : "")}`}
                      style={{
                        background: strength
                          ? `rgba(19, 133, 119, ${0.08 + 0.5 * strength})`
                          : "var(--ceer-bg)",
                        color: "var(--ceer-ink)",
                      }}
                    >
                      {value == null
                        ? "—"
                        : percentage
                          ? `${number(value)}%`
                          : compact(value)}
                    </td>
                  );
                })}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      <Note>
        {percentage
          ? "Colour uses a fixed 0–100% scale. Each column has its own source/window denominator. — means no usable data; 0% means no records for that theme in an available window."
          : "Darker cells indicate higher volume (logarithmic colour scale). Values are counts; hover a cell for the exact count. Zero means no captured activity, not verified platform inactivity."}
      </Note>
    </>
  );
}

export function ActivityCharts({
  resource,
}: {
  resource: Resource<CampaignActivity>;
}) {
  const [mode, setMode] = useState("platforms");
  const [response, setResponse] = useState<"engagements" | "views">(
    "engagements",
  );
  const [heatMetric, setHeatMetric] = useState<"posts" | "engagements">(
    "posts",
  );
  return (
    <>
      <div className={s.controls} style={{ marginBottom: 16 }}>
        <label>
          Line comparison
          <select
            className={s.select}
            aria-label="Line comparison"
            value={mode}
            onChange={(event) => setMode(event.target.value)}
          >
            <option value="platforms">Each social platform</option>
            <option value="total">All channels</option>
          </select>
        </label>
      </div>
      <div className={s.equalGrid} style={{ marginTop: 0 }}>
        {([response, "posts"] as const).map((metric) => (
          <Panel
            key={metric === "posts" ? "posts" : "response"}
            title={
              metric === "posts"
                ? "Social posts over time"
                : metric === "views"
                  ? "Observed views by post date"
                  : "Engagement over time"
            }
            description={
              metric === "posts"
                ? "Published posts for each calendar day in the captured date range."
                : "Accumulated response to posts published on each date—not interactions earned that day."
            }
            action={
              metric !== "posts" ? (
                <select
                  className={s.select}
                  aria-label="Response timeline metric"
                  value={response}
                  onChange={(event) =>
                    setResponse(event.target.value as "engagements" | "views")
                  }
                >
                  <option value="engagements">Engagements</option>
                  <option value="views">Observed views</option>
                </select>
              ) : undefined
            }
          >
            <Load resource={resource} empty={(data) => !data.days.length}>
              {(data) => (
                <>
                  <Chart
                    label={`${metric} by publication date, ${mode === "total" ? "all-channel total" : "individual platform lines"}`}
                  >
                    <ResponsiveContainer width="100%" height="100%">
                      <LineChart
                        data={dailyActivitySeries(data.days, metric)}
                        margin={{ left: 0, right: 12 }}
                      >
                        <CartesianGrid
                          vertical={false}
                          stroke="var(--ceer-line)"
                          strokeDasharray="3 4"
                        />
                        <XAxis
                          {...axis}
                          dataKey="date"
                          tickFormatter={dateLabel}
                          minTickGap={28}
                        />
                        <YAxis
                          {...axis}
                          width={48}
                          tickFormatter={compact}
                          allowDecimals={false}
                        />
                        <Tooltip
                          contentStyle={tooltip}
                          labelFormatter={(label) => dateLabel(String(label))}
                          formatter={(value, name) => [
                            number(Number(value)),
                            name === "total"
                              ? "All channels"
                              : platform(String(name)),
                          ]}
                        />
                        <Legend
                          formatter={(name) =>
                            name === "total" ? "All channels" : platform(name)
                          }
                        />
                        {mode === "total" ? (
                          <Line
                            type="linear"
                            dataKey="total"
                            stroke="#138577"
                            strokeWidth={2.5}
                            dot={false}
                            activeDot={{ r: 4 }}
                            isAnimationActive={false}
                          />
                        ) : (
                          Object.entries(colors)
                            .filter(
                              ([key]) =>
                                metric !== "views" ||
                                data.days.some(
                                  (row) =>
                                    row.platform === key && row.views > 0,
                                ),
                            )
                            .map(([key, color]) => (
                              <Line
                                key={key}
                                type="linear"
                                dataKey={key}
                                stroke={color}
                                strokeWidth={2}
                                dot={false}
                                activeDot={{ r: 4 }}
                                isAnimationActive={false}
                              />
                            ))
                        )}
                      </LineChart>
                    </ResponsiveContainer>
                  </Chart>
                  <Note>
                    {metric === "engagements"
                      ? "Engagements = likes + shares + public comments, including reposts. "
                      : metric === "views"
                        ? "Only channels with positive recorded views contribute. "
                        : "Missing dates within the range show zero captured posts. "}
                    {data.undated_posts > 0
                      ? `${number(data.undated_posts)} undated posts are excluded.`
                      : "All captured posts have usable dates."}
                  </Note>
                </>
              )}
            </Load>
          </Panel>
        ))}
      </div>
      <div className={s.section}>
        <Panel
          title="Platform activity heatmap"
          description="Compare the intensity of publishing and engagement across dates and channels."
          action={
            <select
              className={s.select}
              aria-label="Activity heatmap metric"
              value={heatMetric}
              onChange={(event) =>
                setHeatMetric(event.target.value as "posts" | "engagements")
              }
            >
              <option value="posts">Published posts</option>
              <option value="engagements">Engagements</option>
            </select>
          }
        >
          <Load resource={resource} empty={(data) => !data.days.length}>
            {(data) => {
              const series = dailyActivitySeries(data.days, heatMetric);
              return (
                <Heatmap
                  label={`Platform by date ${heatMetric} heatmap`}
                  columns={series.map((row) => row.date)}
                  rows={Object.keys(colors).map((key) => ({
                    label: platform(key),
                    values: series.map(
                      (row) => row[key as keyof typeof colors],
                    ),
                  }))}
                />
              );
            }}
          </Load>
        </Panel>
      </div>
    </>
  );
}

export function ThemeCharts({
  audience,
  posts,
}: {
  audience: Resource<Theme[]>;
  posts: Resource<Theme[]>;
}) {
  const [source, setSource] = useState("audience");
  const [period, setPeriod] = useState<"before" | "after">("after");
  const [parent, setParent] = useState("all");
  const selected = source === "audience" ? audience : posts;
  const parents = [
    ...new Set(
      (selected.data ?? [])
        .filter((row) => row.comparison_period === period)
        .map((row) => row.theme),
    ),
  ].sort();
  return (
    <>
      <div className={s.section}>
        <Panel
          title="Subtheme explorer"
          description="Top 12 subthemes by share of all records in the selected source and launch window."
          action={
            <div className={s.controls}>
              <label>
                Source
                <select
                  className={s.select}
                  value={source}
                  onChange={(event) => {
                    setSource(event.target.value);
                    setParent("all");
                  }}
                >
                  <option value="audience">Audience comments</option>
                  <option value="posts">Brand posts</option>
                </select>
              </label>
              <label>
                Window
                <select
                  className={s.select}
                  value={period}
                  onChange={(event) => {
                    setPeriod(event.target.value as "before" | "after");
                    setParent("all");
                  }}
                >
                <option value="after">Reveal window</option>
                <option value="before">Pre-reveal window</option>
                </select>
              </label>
              <label>
                Theme
                <select
                  className={s.select}
                  value={parent}
                  onChange={(event) => setParent(event.target.value)}
                >
                  <option value="all">All themes</option>
                  {parents.map((theme) => (
                    <option key={theme}>{theme}</option>
                  ))}
                </select>
              </label>
            </div>
          }
        >
          <Load resource={selected}>
            {(rows) => {
              const data = subthemeSeries(rows, period, parent);
              return data.length ? (
                <>
                  <div style={{ height: Math.max(240, data.length * 34 + 45) }}>
                    <ResponsiveContainer width="100%" height="100%">
                      <BarChart
                        data={data}
                        layout="vertical"
                        margin={{ right: 24 }}
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
                          dataKey="name"
                          width={150}
                          interval={0}
                          tick={{ fill: "var(--ceer-muted)", fontSize: 10 }}
                        />
                        <Tooltip
                          contentStyle={tooltip}
                          formatter={(value, _name, item) => [
                            `${number(Number(value))}% (${number(item.payload.items)} records)`,
                            item.payload.theme,
                          ]}
                        />
                        <Bar
                          dataKey="share"
                          name="Share of window"
                          fill="#138577"
                          radius={[0, 4, 4, 0]}
                          isAnimationActive={false}
                        />
                      </BarChart>
                    </ResponsiveContainer>
                  </div>
                  <Note>
                    Filtering a theme does not change the denominator:
                    percentages remain a share of the entire selected window,
                    not a share within that theme.
                  </Note>
                </>
              ) : (
                <p className={s.empty}>
                  No subthemes available for this selection.
                </p>
              );
            }}
          </Load>
        </Panel>
      </div>
      <div className={s.section}>
        <Panel
          title="Theme attention heatmap"
          description="Theme shares across launch windows and sources. Compare audience attention with the content being published."
        >
          <Load resource={audience}>
            {(comments) => (
              <Load resource={posts}>
                {(content) => (
                  <Heatmap
                    label="Theme shares by source and launch window"
                    percentage
                    columns={[
                      "Audience before",
                      "Audience after",
                      "Posts before",
                      "Posts after",
                    ]}
                    rows={themeMatrix(comments, content)}
                  />
                )}
              </Load>
            )}
          </Load>
        </Panel>
      </div>
    </>
  );
}
