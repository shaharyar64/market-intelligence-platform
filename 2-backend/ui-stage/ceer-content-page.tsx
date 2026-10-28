"use client";

import { useState } from "react";
import Image from "next/image";
import { ArrowUpRight } from "lucide-react";
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
import {
  getActivity,
  getBeforeAfterMetrics,
  getContentPerformance,
  getTopPosts,
  type CampaignPlatform,
} from "@/lib/ceerCampaign";
import { ActivityCharts } from "../extra-charts";
import { useAsyncResource } from "@/lib/useAsyncResource";
import {
  axis,
  CampaignShell,
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
} from "../shared";

export default function CampaignContent() {
  const [channel, setChannel] = useState<CampaignPlatform>("all");
  const [ranking, setRanking] = useState<"views" | "engagement">("views");
  const activity = useAsyncResource(getActivity, []);
  const performance = useAsyncResource(getContentPerformance, []);
  const launch = useAsyncResource(getBeforeAfterMetrics, []);
  const top = useAsyncResource(
    (signal) => getTopPosts(signal, channel, ranking),
    [channel, ranking],
  );

  return (
    <CampaignShell
      title="Content signals, in context."
      description="Publishing rhythm and observable response across captured launch posts."
    >
      <ActivityCharts resource={activity} />

      <section
        className={s.creativeStory}
        aria-labelledby="creative-story-title"
      >
        <div className={s.creativeStoryCopy}>
          <span>Reveal visual language</span>
          <h2 id="creative-story-title">
            Designed for the pause before the scroll.
          </h2>
          <p>
            Studio light, reveal theatre and a technology-led cockpit gave the
            launch a recognisable visual system across formats.
          </p>
        </div>
        <figure className={s.creativeWide}>
          <Image
            src="/ceer/exobot-studio.webp"
            alt="CEER EXOBOT Sedan in an architectural studio"
            fill
            sizes="(max-width: 900px) 100vw, 46vw"
          />
          <figcaption>Exterior presence</figcaption>
        </figure>
        <div className={s.creativeStack}>
          <figure>
            <Image
              src="/ceer/exobot-reveal.webp"
              alt="Front view of a CEER EXOBOT during its reveal"
              fill
              sizes="(max-width: 900px) 50vw, 22vw"
            />
            <figcaption>Reveal theatre</figcaption>
          </figure>
          <figure>
            <Image
              src="/ceer/exobot-cockpit.webp"
              alt="Technology-focused interior of the CEER EXOBOT"
              fill
              sizes="(max-width: 900px) 50vw, 22vw"
            />
            <figcaption>Digital cockpit</figcaption>
          </figure>
        </div>
      </section>

      <div className={s.equalGrid}>
        <Panel
          title="A typical post—or a viral outlier?"
          description="Reveal-window average versus median likes per post."
        >
          <Load resource={launch}>
            {(rows) => (
              <>
                <Chart label="Average and median likes per post in the reveal window">
                  <ResponsiveContainer width="100%" height="100%">
                    <BarChart
                      data={rows.map((row) => ({
                        channel: platform(row.platform),
                        Average: row.likes_per_post_after,
                        Median: row.median_likes_after,
                      }))}
                    >
                      <CartesianGrid
                        vertical={false}
                        stroke="var(--ceer-line)"
                        strokeDasharray="3 4"
                      />
                      <XAxis {...axis} dataKey="channel" />
                      <YAxis {...axis} width={48} tickFormatter={compact} />
                      <Tooltip
                        contentStyle={tooltip}
                        formatter={(value) => number(Number(value))}
                      />
                      <Legend />
                      <Bar
                        dataKey="Average"
                        fill="#5879bb"
                        radius={[4, 4, 0, 0]}
                      />
                      <Bar
                        dataKey="Median"
                        fill="#138577"
                        radius={[4, 4, 0, 0]}
                      />
                    </BarChart>
                  </ResponsiveContainer>
                </Chart>
                <Note>
                  A large gap suggests results are concentrated in a few posts.
                  The median describes the middle post, not the average.
                </Note>
              </>
            )}
          </Load>
        </Panel>
        <Panel
          title="How people engaged"
          description="The share of interactions that were likes, shares, or comments."
        >
          <Load resource={performance}>
            {(rows) => (
              <>
                <Chart label="Engagement composition by channel">
                  <ResponsiveContainer width="100%" height="100%">
                    <BarChart
                      layout="vertical"
                      data={rows.map((row) => {
                        const total = row.likes + row.shares + row.comments;
                        return {
                          channel: platform(row.platform),
                          Likes: total ? (row.likes / total) * 100 : 0,
                          Shares: total ? (row.shares / total) * 100 : 0,
                          Comments: total ? (row.comments / total) * 100 : 0,
                        };
                      })}
                      margin={{ left: 4, right: 10 }}
                    >
                      <XAxis
                        {...axis}
                        type="number"
                        domain={[0, 100]}
                        unit="%"
                      />
                      <YAxis
                        {...axis}
                        type="category"
                        dataKey="channel"
                        width={73}
                      />
                      <Tooltip
                        contentStyle={tooltip}
                        formatter={(value) => `${Number(value).toFixed(1)}%`}
                      />
                      <Legend />
                      <Bar dataKey="Likes" stackId="mix" fill="#5879bb" />
                      <Bar dataKey="Shares" stackId="mix" fill="#138577" />
                      <Bar
                        dataKey="Comments"
                        stackId="mix"
                        fill="#a65a88"
                        radius={[0, 4, 4, 0]}
                      />
                    </BarChart>
                  </ResponsiveContainer>
                </Chart>
                <Note>
                  Interaction mix, not an engagement rate: there is no common
                  reach denominator across all channels. Reposts can dominate
                  totals.
                </Note>
              </>
            )}
          </Load>
        </Panel>
      </div>

      <div className={s.section}>
        <Panel
          title="Content leaderboard"
          description="Top 12 records from the captured launch dataset. Change the channel or ranking to explore beyond the biggest view counts."
          action={
            <div className={s.controls}>
              <label>
                Channel
                <select
                  className={s.select}
                  value={channel}
                  onChange={(e) =>
                    setChannel(e.target.value as CampaignPlatform)
                  }
                >
                  <option value="all">All channels</option>
                  {Object.keys(colors).map((key) => (
                    <option key={key} value={key}>
                      {platform(key)}
                    </option>
                  ))}
                </select>
              </label>
              <label>
                Rank by
                <select
                  className={s.select}
                  value={ranking}
                  onChange={(e) =>
                    setRanking(e.target.value as "views" | "engagement")
                  }
                >
                  <option value="views">Observed views</option>
                  <option value="engagement">Engagements</option>
                </select>
              </label>
            </div>
          }
        >
          <Load resource={top}>
            {(posts) => (
              <div className={s.postList}>
                {posts.map((post, index) => (
                  <article
                    key={`${post.platform}-${post.post_id}`}
                    className={s.post}
                  >
                    <div className={s.postHead}>
                      <span className={s.platform}>
                        <span>{String(index + 1).padStart(2, "0")}</span>
                        <i
                          className={s.dot}
                          style={{
                            background:
                              colors[post.platform as keyof typeof colors],
                          }}
                        />
                        {platform(post.platform)}
                      </span>
                      {post.post_url && /^https?:\/\//i.test(post.post_url) ? (
                        <a
                          href={post.post_url}
                          target="_blank"
                          rel="noreferrer"
                          aria-label={`Open ${platform(post.platform)} post ranked ${index + 1}`}
                        >
                          <ArrowUpRight size={17} />
                        </a>
                      ) : null}
                    </div>
                    <p
                      className={s.postText}
                      dir="auto"
                      title={post.post_text ?? undefined}
                    >
                      {post.post_text || "No caption captured."}
                    </p>
                    <span className={s.tag}>
                      {post.sub_theme || post.theme || "Unclassified content"}
                    </span>
                    <div className={s.postStats}>
                      <div>
                        <strong>
                          {post.views == null ? "—" : compact(post.views)}
                        </strong>
                        <small>
                          {post.views == null
                            ? "Views not reported"
                            : post.views === 0
                              ? "No positive views recorded"
                              : "Observed views"}
                        </small>
                      </div>
                      <div>
                        <strong>
                          {compact(post.likes + post.shares + post.comments)}
                        </strong>
                        <small>Engagements</small>
                      </div>
                    </div>
                    <Note>
                      {compact(post.likes)} likes · {compact(post.shares)}{" "}
                      shares · {compact(post.comments)} comments
                    </Note>
                  </article>
                ))}
              </div>
            )}
          </Load>
        </Panel>
      </div>
    </CampaignShell>
  );
}
