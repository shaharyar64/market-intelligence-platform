import { apiFetch } from "./apiClient";

export type CampaignKpis = {
  followers: number;
  posts: number;
  likes: number;
  shares: number;
  public_comments: number;
  views: number;
  collected_comments: number;
  social_collected_comments: number;
  youtube_collected_comments: number;
};

export type PlatformOverview = {
  platform: string;
  followers: number;
  total_posts: number;
  total_likes: number;
  total_shares: number;
  public_comment_count: number;
  total_views: number;
  collected_comments: number;
};

export type CampaignOverview = {
  kpis: CampaignKpis;
  platforms: PlatformOverview[];
};

export type BeforeAfterMetric = {
  platform: string;
  posts_before: number;
  posts_after: number;
  total_likes_before: number;
  total_likes_after: number;
  likes_per_post_before: number | null;
  likes_per_post_after: number | null;
  public_comments_per_post_before: number | null;
  public_comments_per_post_after: number | null;
  views_per_observed_post_before: number | null;
  views_per_observed_post_after: number | null;
  median_likes_before: number | null;
  median_likes_after: number | null;
  posts_per_day_change_pct: number | null;
  likes_per_post_change_pct: number | null;
  public_comments_per_post_change_pct: number | null;
  views_per_observed_post_change_pct: number | null;
};

export type LaunchImpactMetric = {
  period: "before" | "launch_day" | "after";
  start_date: string;
  end_date: string;
  posts: number;
  likes: number;
  comments: number;
  shares: number;
  views: number;
  engagements: number;
  engagements_per_post: number | null;
};

export type LaunchTheme = {
  period: "before" | "launch_day" | "after";
  theme: string;
  items: number;
  period_items: number;
  share_pct: number;
};

export type Sentiment = {
  comparison_period: "before" | "launch_day" | "after";
  sentiment: "positive" | "neutral" | "negative";
  comments: number;
  usable_comments: number;
  share_pct: number;
};

export type Theme = {
  comparison_period: "before" | "after";
  theme: string;
  sub_theme: string;
  items: number;
  period_items: number;
  share_pct: number;
};

export type ContentPerformance = {
  platform: string;
  posts: number;
  posts_with_views: number;
  likes: number;
  shares: number;
  comments: number;
  views: number;
};

export type TopPost = {
  post_id: string;
  platform: string;
  post_url: string | null;
  post_text: string | null;
  likes: number;
  shares: number;
  comments: number;
  views: number | null;
  theme: string | null;
  sub_theme: string | null;
};
export type Comment = {
  comment_id: string;
  platform: string;
  comment_text: string;
  likes: number;
  replies: number;
  theme: string | null;
  sub_theme: string | null;
};
export type Feed<T> = { items: T[]; total: number };
export type CompetitorMentions = {
  references: {
    reference: string;
    typical_comparison: string;
    mentions: number;
    comparisons: number;
    likes: number;
  }[];
  examples: {
    comment_id: string;
    platform: string;
    comment_text: string;
    likes: number;
    reference: string;
    is_comparison: boolean;
  }[];
};

export type CommunityPulse = {
  platform: string;
  comments: number;
  comment_likes: number;
  themes: number;
};

export type AudienceTheme = {
  theme: string;
  sub_theme: string;
  items: number;
  total_items: number;
  share_pct: number;
};

export type CampaignPlatform =
  | "all"
  | "instagram"
  | "linkedin"
  | "tiktok"
  | "twitter";
export type ActivityDay = {
  date: string;
  platform: string;
  posts: number;
  views: number;
  engagements: number;
};
export type CampaignActivity = { days: ActivityDay[]; undated_posts: number };

export type SearchInterest = {
  date: string;
  keyword: string;
  country: string;
  interest: number;
};

export type SearchRegion = {
  keyword: string;
  geo_code: string;
  geo_name: string;
  country: string;
  score: number;
};

export type SearchKeyword = "ceer" | "exobot";

async function getJson<T>(path: string, signal?: AbortSignal): Promise<T> {
  const controller = new AbortController();
  const abort = () => controller.abort();
  signal?.addEventListener("abort", abort, { once: true });
  if (signal?.aborted) controller.abort();
  let timer: ReturnType<typeof setTimeout> | undefined;
  const deadline = new Promise<never>((_, reject) => {
    timer = setTimeout(() => {
      reject(new Error("Campaign data is taking too long. Retry this panel."));
      controller.abort();
    }, 45_000);
  });
  try {
    return await Promise.race([
      deadline,
      (async () => {
        const response = await apiFetch(
          `/api/v1/ceer-campaign/campaign/${path}`,
          { signal: controller.signal },
        );
        if (!response.ok)
          throw new Error(
            `Campaign data could not be loaded (${response.status}). Retry this panel.`,
          );
        return response.json() as Promise<T>;
      })(),
    ]);
  } finally {
    clearTimeout(timer);
    signal?.removeEventListener("abort", abort);
  }
}

export const getCampaignOverview = (signal?: AbortSignal) =>
  getJson<CampaignOverview>("overview", signal);
export const getBeforeAfterMetrics = (signal?: AbortSignal) =>
  getJson<BeforeAfterMetric[]>("before-after", signal);
export const getLaunchImpact = (signal?: AbortSignal) =>
  getJson<LaunchImpactMetric[]>("launch-impact", signal);
export const getLaunchThemes = (signal?: AbortSignal) =>
  getJson<LaunchTheme[]>("launch-themes", signal);
export const getSentiment = (signal?: AbortSignal) =>
  getJson<Sentiment[]>("sentiment", signal);
export const getThemes = (
  contentType: "post" | "audience_comment",
  signal?: AbortSignal,
) => getJson<Theme[]>(`themes?content_type=${contentType}`, signal);
export const getContentPerformance = (signal?: AbortSignal) =>
  getJson<ContentPerformance[]>("content-performance", signal);
export const getTopPosts = (
  signal?: AbortSignal,
  platform: CampaignPlatform = "all",
  sort: "views" | "engagement" = "views",
) =>
  getJson<TopPost[]>(
    `top-posts?limit=12&platform=${platform}&sort=${sort}`,
    signal,
  );
export const getPostsFeed = (mode: "top" | "all", platform: CampaignPlatform, period: "all" | "before" | "launch_day" | "after", theme: string, signal?: AbortSignal) =>
  getJson<Feed<TopPost>>(`posts?mode=${mode}&limit=${mode === "all" ? 100 : 12}&platform=${platform}&period=${period}&theme=${encodeURIComponent(theme)}`, signal);
export const getCommentsFeed = (mode: "top" | "all", signal?: AbortSignal) =>
  getJson<Feed<Comment>>(`comments?mode=${mode}&limit=${mode === "all" ? 50 : 12}`, signal);
export const getCommunityPulse = (signal?: AbortSignal) =>
  getJson<CommunityPulse[]>("community-pulse", signal);
export const getAllAudienceThemes = (signal?: AbortSignal) =>
  getJson<AudienceTheme[]>("audience-themes", signal);
export const getCompetitorMentions = (signal?: AbortSignal) => getJson<CompetitorMentions>("competitor-mentions", signal);
export const getActivity = (signal?: AbortSignal) =>
  getJson<CampaignActivity>("activity", signal);
export const getSearchInterest = async (
  keyword: SearchKeyword,
  signal?: AbortSignal,
) =>
  (
    await getJson<{ data: SearchInterest[] }>(
      `search-interest?keyword=${encodeURIComponent(keyword)}`,
      signal,
    )
  ).data;
export const getSearchRegions = async (
  keyword: SearchKeyword,
  signal?: AbortSignal,
) =>
  (
    await getJson<{ data: SearchRegion[] }>(
      `search-regions?keyword=${encodeURIComponent(keyword)}`,
      signal,
    )
  ).data;
