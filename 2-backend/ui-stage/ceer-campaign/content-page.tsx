"use client";

import { useState } from "react";
import Image from "next/image";
import { ArrowUpRight } from "lucide-react";
import {
  Bar,
  BarChart,
  Legend,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import {
  getActivity,
  getContentPerformance,
  getPostsFeed,
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
  Panel,
  platform,
  s,
  tooltip,
} from "../shared";

export default function CampaignContent() {
  const [postView, setPostView] = useState<"top" | "all">("top");
  const [channel, setChannel] = useState<CampaignPlatform>("all");
  const [period, setPeriod] = useState<"all" | "before" | "launch_day" | "after">("all");
  const [theme, setTheme] = useState("all");
  const activity = useAsyncResource(getActivity, []);
  const performance = useAsyncResource(getContentPerformance, []);
  const top = useAsyncResource(
    (signal) => getPostsFeed(postView, channel, period, theme, signal),
    [postView, channel, period, theme],
  );

  return (
    <CampaignShell
      title="Post performance"
      description="Posts and engagement across CEER’s launch channels."
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

      <div className={s.section}>
        <Panel
          title="Engagement breakdown"
          description="How likes, shares, and comments contribute to engagement."
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
          title={postView === "top" ? "Top posts" : "All posts"}
          description={postView === "top" ? "Best-performing posts in the captured launch data." : "All captured CEER launch posts."}
          action={
            <div className={s.feedToolbar}>
              <div className={s.searchTabs}>
                {(["top", "all"] as const).map((view) => (
                  <button key={view} type="button" className={postView === view ? s.searchTabActive : s.searchTab} onClick={() => setPostView(view)}>
                    {view === "top" ? "Top posts" : "All posts"}
                  </button>
                ))}
              </div>
              <div className={s.filterGroup}>
                <label className={s.filterLabel}>Channel<select className={s.select} value={channel} onChange={(event) => setChannel(event.target.value as CampaignPlatform)}><option value="all">All channels</option>{Object.keys(colors).map((key) => <option key={key} value={key}>{platform(key)}</option>)}</select></label>
                <label className={s.filterLabel}>Period<select className={s.select} value={period} onChange={(event) => setPeriod(event.target.value as typeof period)}><option value="all">All periods</option><option value="before">Week before</option><option value="launch_day">Launch day</option><option value="after">Week after</option></select></label>
                <label className={s.filterLabel}>Theme<select className={s.select} value={theme} onChange={(event) => setTheme(event.target.value)}><option value="all">All themes</option><option>Brand &amp; Market Perception</option><option>Launch &amp; Brand Narrative</option><option>Saudi Brand &amp; Industrial Impact</option><option>Exterior Design &amp; Product Form</option><option>Ownership &amp; Commercial Access</option><option>Electric Capability &amp; Regional Readiness</option><option>Digital Technology &amp; Safety</option><option>Cabin &amp; Passenger Experience</option></select></label>
              </div>
            </div>
          }
        >
          <Load resource={top}>
            {({ items: posts, total }) => (
              <>
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
              <Note>Showing {posts.length} of {total} posts.</Note>
              </>
            )}
          </Load>
        </Panel>
      </div>
    </CampaignShell>
  );
}
