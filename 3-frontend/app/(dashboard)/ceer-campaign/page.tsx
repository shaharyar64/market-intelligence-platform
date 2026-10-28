"use client";

import { useState } from "react";
import LaunchImpactPage from "./launch-impact";
import Image from "next/image";
import dynamic from "next/dynamic";
import {
  ArrowUpRight,
  Eye,
  Heart,
  MessageCircle,
  Share2,
  Users,
  Video,
} from "lucide-react";
import {
  Bar,
  BarChart,
  CartesianGrid,
  Cell,
  Legend,
  Line,
  LineChart,
  Pie,
  PieChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import {
  getBeforeAfterMetrics,
  getCampaignOverview,
  getContentPerformance,
  getSearchInterest,
  getSearchRegions,
  type SearchKeyword,
} from "@/lib/ceerCampaign";
import { searchInterestSeries } from "@/lib/ceerCampaignAnalysis";
import { useAsyncResource } from "@/lib/useAsyncResource";
import {
  axis,
  CampaignShell,
  Chart,
  colors,
  compact,
  Load,
  MoreLink,
  Note,
  number,
  Panel,
  platform,
  s,
  tooltip,
} from "./shared";

const CeerSearchMap = dynamic(() => import("@/components/maps/CeerSearchMap"), {
  ssr: false,
  loading: () => <div className={s.loading}>Loading regional map…</div>,
});

const searchColors = ["#087d79", "#5879bb", "#a65a88", "#b17a37", "#697582"];
const searchKeywords: SearchKeyword[] = ["ceer", "exobot"];
const trendDate = (date: string) =>
  new Date(`${date}T00:00:00Z`).toLocaleDateString("en", {
    day: "numeric",
    month: "short",
    timeZone: "UTC",
  });

const measures = {
  totalLikes: {
    label: "Total likes",
    before: "total_likes_before",
    after: "total_likes_after",
  },
  likes: {
    label: "Likes per post",
    before: "likes_per_post_before",
    after: "likes_per_post_after",
  },
  comments: {
    label: "Comments per post",
    before: "public_comments_per_post_before",
    after: "public_comments_per_post_after",
  },
  views: {
    label: "Views per observed post",
    before: "views_per_observed_post_before",
    after: "views_per_observed_post_after",
  },
} as const;

export function LegacyCeerCampaignPage() {
  const overview = useAsyncResource(getCampaignOverview, []);
  const launch = useAsyncResource(getBeforeAfterMetrics, []);
  const content = useAsyncResource(getContentPerformance, []);
  const [measure, setMeasure] = useState<keyof typeof measures>("totalLikes");
  const [searchKeyword, setSearchKeyword] = useState<SearchKeyword>("ceer");
  const searchInterest = useAsyncResource(
    (signal) => getSearchInterest(searchKeyword, signal),
    [searchKeyword],
  );
  const searchRegions = useAsyncResource(
    (signal) => getSearchRegions(searchKeyword, signal),
    [searchKeyword],
  );
  const chosen = measures[measure];
  const searchLabel = searchKeyword.toUpperCase();

  return (
    <CampaignShell
      title="The launch, in focus."
      description="A market-signal read of the public activity around CEER EXOBOT’s first vehicle reveal."
    >
      <section
        className={s.launchHero}
        aria-label="CEER EXOBOT launch signal study"
      >
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
          <span>EXOBOT launch signal study</span>
          <h2>One reveal. Two silhouettes. A new Saudi automotive story.</h2>
          <p>Observable owned-channel and search signals around the reveal.</p>
        </div>
        <div className={s.launchHeroIndex} aria-hidden="true">
          <span>01</span>
          <i />
          <span>02</span>
        </div>
      </section>

      <section className={s.vehicles} aria-label="CEER EXOBOT vehicles">
        {(["sedan", "suv"] as const).map((vehicle) => (
          <a
            className={s.vehicle}
            key={vehicle}
            href={`https://ceermotors.com/exobot/${vehicle}/`}
            target="_blank"
            rel="noreferrer"
            aria-label={`Explore the official CEER EXOBOT ${vehicle === "suv" ? "SUV" : "Sedan"}`}
          >
            <div className={s.vehicleHeader}>
              <div>
                <h2>EXOBOT {vehicle === "suv" ? "SUV" : "Sedan"}</h2>
                <p>CEER’s electric debut</p>
              </div>
              <span>Vehicle reveal</span>
            </div>
            <Image
              src={`/ceer/exobot-${vehicle}.png`}
              alt={`Official CEER EXOBOT ${vehicle} side profile`}
              width={1000}
              height={vehicle === "suv" ? 367 : 297}
              className={s.vehicleImage}
              priority
            />
            <div className={s.vehicleCaption}>
              <span>Explore the design</span>
              <ArrowUpRight size={14} />
            </div>
          </a>
        ))}
      </section>
      <p className={s.credit}>
        Vehicle imagery ©{" "}
        <a href="https://ceermotors.com/" target="_blank" rel="noreferrer">
          CEER
        </a>
        . Visuals are not model-level signal attribution.
      </p>

      <Load resource={overview} empty={(data) => !data.platforms.length}>
        {({ kpis }) => (
          <section className={s.metrics} aria-label="Launch study totals">
            {[
              {
                label: "Observed views",
                value: kpis.views,
                detail: "Reported views only",
                Icon: Eye,
              },
              {
                label: "Followers",
                value: kpis.followers,
                detail: "Across channel accounts",
                Icon: Users,
              },
              {
                label: "Published posts",
                value: kpis.posts,
                detail: "Captured launch dataset",
                Icon: Video,
              },
              {
                label: "Likes",
                value: kpis.likes,
                detail: "Includes reposts",
                Icon: Heart,
              },
              {
                label: "Shares",
                value: kpis.shares,
                detail: "Recorded interactions",
                Icon: Share2,
              },
              {
                label: "Collected comments",
                value: kpis.collected_comments,
                detail: "Available for audience analysis",
                Icon: MessageCircle,
              },
            ].map(({ label, value, detail, Icon }) => (
              <div className={s.metric} key={label}>
                <div className={s.metricLabel}>
                  <Icon size={13} />
                  {label}
                </div>
                <strong title={number(value)}>{compact(value)}</strong>
                <small>{detail}</small>
              </div>
            ))}
          </section>
        )}
      </Load>

      <div className={s.grid}>
        <Panel
          title="How response differed across the launch windows"
          description="A descriptive comparison of the seven-day pre-reveal and reveal windows, not causal attribution."
          action={
            <select
              className={s.select}
              aria-label="Launch comparison metric"
              value={measure}
              onChange={(e) =>
                setMeasure(e.target.value as keyof typeof measures)
              }
            >
              {Object.entries(measures).map(([key, item]) => (
                <option key={key} value={key}>
                  {item.label}
                </option>
              ))}
            </select>
          }
        >
          <Load resource={launch}>
            {(rows) => (
              <>
                <Chart
                  label={`${chosen.label}, pre-reveal versus reveal window by platform`}
                >
                  <ResponsiveContainer width="100%" height="100%">
                    <BarChart
                      data={rows.map((row) => ({
                        platform: platform(row.platform),
                        Before: row[chosen.before],
                        After: row[chosen.after],
                      }))}
                      barGap={6}
                      margin={{ left: 0, right: 4 }}
                    >
                      <CartesianGrid
                        vertical={false}
                        stroke="var(--ceer-line)"
                        strokeDasharray="3 4"
                      />
                      <XAxis {...axis} dataKey="platform" />
                      <YAxis {...axis} tickFormatter={compact} width={48} />
                      <Tooltip
                        contentStyle={tooltip}
                        formatter={(value) => number(Number(value))}
                      />
                      <Legend />
                      <Bar
                        dataKey="Before"
                        name="Pre-reveal"
                        fill="#a8b8c4"
                        radius={[4, 4, 0, 0]}
                      />
                      <Bar
                        dataKey="After"
                        name="Reveal window"
                        fill="#138577"
                        radius={[4, 4, 0, 0]}
                      />
                    </BarChart>
                  </ResponsiveContainer>
                </Chart>
                <Note>
                  Pre-reveal: {rows.reduce((sum, row) => sum + row.posts_before, 0)}{" "}
                  posts. Reveal window: {rows.reduce((sum, row) => sum + row.posts_after, 0)} posts. {measure === "totalLikes"
                    ? "Total likes reflect both publishing volume and response; choose a per-post view for efficiency."
                    : "Per-post differences are descriptive and do not establish that the reveal caused the change."}
                </Note>
              </>
            )}
          </Load>
        </Panel>
        <Panel
          title="Where reported views came from"
          description="Share of positive view records by channel. Availability differs by platform."
        >
          <Load resource={content}>
            {(rows) => {
              const observed = rows.filter((row) => row.posts_with_views > 0);
              const total = observed.reduce((sum, row) => sum + row.views, 0);
              return (
                <>
                  {total > 0 ? (
                    <Chart label="Share of reported views by platform">
                      <ResponsiveContainer width="100%" height="100%">
                        <PieChart>
                          <Pie
                            data={observed}
                            dataKey="views"
                            nameKey="platform"
                            innerRadius={70}
                            outerRadius={104}
                            paddingAngle={3}
                            stroke="none"
                          >
                            {observed.map((row) => (
                              <Cell
                                key={row.platform}
                                fill={
                                  colors[row.platform as keyof typeof colors] ??
                                  colors.twitter
                                }
                              />
                            ))}
                          </Pie>
                          <Tooltip
                            contentStyle={tooltip}
                            formatter={(value, name) => [
                              number(Number(value)),
                              platform(String(name)),
                            ]}
                          />
                        </PieChart>
                      </ResponsiveContainer>
                    </Chart>
                  ) : (
                    <p className={s.empty}>No observed views available.</p>
                  )}
                  <div className={s.legend} aria-label="View reporting coverage">
                    {rows.map((row) => (
                      <span key={row.platform}>
                        <i
                          className={s.dot}
                          style={{
                            background:
                              colors[row.platform as keyof typeof colors],
                          }}
                        />
                        {platform(row.platform)}{" "}
                        <strong>
                          {row.posts_with_views
                            ? `${total ? ((row.views / total) * 100).toFixed(1) : "0"}% of reported views`
                            : "Not reported"}
                        </strong>
                      </span>
                    ))}
                  </div>
                  <Note>
                    Reported views: {observed.map((row) => platform(row.platform)).join(" and ")}.{" "}
                    No view data supplied: {" "}
                    {rows
                      .filter((row) => !row.posts_with_views)
                      .map((row) => platform(row.platform))
                      .join(" and ") || "none"}. Missing view data does not mean zero views.
                  </Note>
                </>
              );
            }}
          </Load>
        </Panel>
      </div>

      <div className={s.section}>
        <div className={s.searchTabs} role="tablist" aria-label="Search term">
          {searchKeywords.map((keyword) => (
            <button
              key={keyword}
              type="button"
              role="tab"
              aria-selected={searchKeyword === keyword}
              className={searchKeyword === keyword ? s.searchTabActive : s.searchTab}
              onClick={() => setSearchKeyword(keyword)}
            >
              {keyword.toUpperCase()}
            </button>
          ))}
        </div>
        <Panel
          title={`${searchLabel} search interest around the reveal`}
          description={`Google Trends interest for ${searchLabel}. This is external search demand, not social engagement.`}
        >
          <Load resource={searchInterest}>
            {(rows) => {
              const series = searchInterestSeries(rows);
              return (
                <>
                  <Chart label="Google Trends search interest over time">
                    <ResponsiveContainer width="100%" height="100%">
                      <LineChart data={series.data} margin={{ left: 0, right: 8 }}>
                        <CartesianGrid
                          vertical={false}
                          stroke="var(--ceer-line)"
                          strokeDasharray="3 4"
                        />
                        <XAxis
                          {...axis}
                          dataKey="date"
                          tickFormatter={trendDate}
                        />
                        <YAxis {...axis} domain={[0, 100]} width={34} />
                        <Tooltip
                          contentStyle={tooltip}
                          labelFormatter={(label) => trendDate(String(label))}
                          formatter={(value) => number(Number(value))}
                        />
                        <Legend />
                        {series.keys.map((key, index) => (
                          <Line
                            key={key}
                            type="monotone"
                            dataKey={key}
                            name={key}
                            stroke={searchColors[index]}
                            strokeWidth={2}
                            dot={false}
                            connectNulls
                          />
                        ))}
                      </LineChart>
                    </ResponsiveContainer>
                  </Chart>
                  <Note>
                    Google Trends values are indexed search interest, not search
                    volume.
                  </Note>
                </>
              );
            }}
          </Load>
        </Panel>
        <Panel
          title={`Where ${searchLabel} search interest is strongest`}
          description={`Latest Google Trends regional snapshot for ${searchLabel} across Saudi Arabia. Province fill colour shows relative interest.`}
        >
          <Load resource={searchRegions}>
            {(rows) => (
              <>
                <CeerSearchMap data={rows} />
                <Note>
                  Hover a province for its score. Regional Trends scores are
                  relative within the selected snapshot.
                </Note>
              </>
            )}
          </Load>
        </Panel>
      </div>

      <div className={s.section}>
        <Panel
          title="Channel data coverage"
          description="What is available for each channel, separate from the response comparison above."
          action={
            <MoreLink href="/ceer-campaign/content">Explore content</MoreLink>
          }
        >
          <Load resource={overview}>
            {({ platforms }) => (
              <>
                <div className={s.tableWrap}>
                  <table className={s.table}>
                    <thead>
                      <tr>
                        <th>Channel</th>
                        <th>Captured posts</th>
                        <th>Comments collected</th>
                        <th>View data</th>
                        <th>Window status</th>
                      </tr>
                    </thead>
                    <tbody>
                      {platforms.map((row) => (
                        <tr key={row.platform}>
                          <td>
                            <span className={s.platform}>
                              <i
                                className={s.dot}
                                style={{
                                  background:
                                    colors[row.platform as keyof typeof colors],
                                }}
                              />
                              {platform(row.platform)}
                            </span>
                          </td>
                          <td>{number(row.total_posts)}</td>
                          <td>{number(row.collected_comments)}</td>
                          <td>{row.total_views > 0 ? "Reported" : "Not reported"}</td>
                          <td>Comparable</td>
                        </tr>
                      ))}
                      <tr>
                        <td>
                          <span className={s.platform}>
                            <i className={s.dot} style={{ background: "#b65357" }} />
                            YouTube
                          </span>
                        </td>
                        <td>—</td>
                        <td>Thematic context</td>
                        <td>Not reported</td>
                        <td>Undated</td>
                      </tr>
                    </tbody>
                  </table>
                </div>
                <Note>
                  YouTube comments are available as thematic context, but video
                  publication dates were not captured, so they cannot be
                  compared in the pre-reveal and reveal windows.
                </Note>
              </>
            )}
          </Load>
        </Panel>
      </div>
    </CampaignShell>
  );
}

export default LaunchImpactPage;
