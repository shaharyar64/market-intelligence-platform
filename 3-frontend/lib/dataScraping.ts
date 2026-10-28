import { apiFetch } from "@/lib/apiClient";

export type InstagramProfileScrapeRequest = {
  usernames: string[];
  include_about_section?: boolean;
  country: string;
  industry: string;
  project: string;
  save_to_database: boolean;
};

export type InstagramProfileScrapeRow = {
  id: number | string;
  username: string;
  full_name: string;
  followers: number;
  following: number;
  posts: number;
  category: string;
  is_verified: boolean;
  bio: string;
  external_url: string;
  last_updated: string;
  country: string;
  industry: string;
  project: string;
};

export type InstagramPostScrapeRequest = {
  usernames: string[];
  start_date: string;
  end_date: string;
  save_to_database: boolean;
  upload_images_to_s3: boolean;
};

export type InstagramPostScrapeRow = {
  id: string;
  username: string;
  uploaded_at: string;
  caption: string;
  views: number;
  comments: number;
  likes: number;
  last_updated: string;
  thumbnail_url?: string | null;
  s3_key?: string | null;
  image_upload_status?: string | null;
};

export type LinkedinProfileScrapeRequest = {
  profile_urls: string[];
  country: string;
  project: string;
  save_to_database: boolean;
};

export type LinkedinProfileScrapeRow = {
  url: string;
  company_name: string;
  website_url?: string | null;
  industry?: string | null;
  employee_count: number;
  follower_count: number;
  universal_name?: string | null;
  tagline?: string | null;
  hashtag?: string | null;
  country?: string | null;
  city?: string | null;
  postal_code?: string | null;
  founded_on?: string | null;
  description?: string | null;
  project?: string | null;
  last_updated: string;
};

export type LinkedinPostScrapeRequest = {
  target_urls: string[];
  start_date: string;
  end_date: string;
  max_posts: number;
  save_to_database: boolean;
};

export type LinkedinPostScrapeRow = {
  post_text?: string | null;
  post_url: string;
  likes: number;
  shares: number;
  comments: number;
  uploaded_at: string;
  universal_name?: string | null;
  source_company?: string | null;
  last_updated: string;
};

export type TwitterProfileScrapeRequest = {
  usernames: string[];
  country: string;
  industry: string;
  project: string;
  save_to_database: boolean;
};

export type TwitterProfileScrapeRow = {
  id: number | string;
  username: string;
  full_name: string;
  bio?: string | null;
  followers: number;
  following: number;
  posts: number;
  is_verified: boolean;
  is_blue_verified: boolean;
  verified_type?: string | null;
  created_at: string;
  last_updated: string;
  country: string;
  industry: string;
  project?: string | null;
};

export type TwitterPostScrapeRequest = {
  usernames: string[];
  start_date: string;
  end_date: string;
  save_to_database: boolean;
};

export type TwitterPostScrapeRow = {
  id: string;
  username: string;
  text: string;
  uploaded_at: string;
  views: number;
  replies: number;
  retweet: number;
  likes: number;
  last_updated: string;
};

export type TwitterKeywordScrapeRequest = {
  keywords: string[];
  start_date: string;
  end_date: string;
  query_type: string;
  lang: string | null;
  location_query: string | null;
  filter_by_country: boolean;
  country_filter_terms: string[];
  exclude_retweets: boolean;
  exclude_replies: boolean;
  window_days: number;
  max_pages_per_window: number | null;
  project: string;
  country: string;
  industry: string;
  save_to_database: boolean;
};

export type TwitterKeywordScrapeRow = TwitterPostScrapeRow & {
  keyword?: string | null;
  query?: string | null;
  country?: string | null;
  industry?: string | null;
  project?: string | null;
  lang?: string | null;
  location_query?: string | null;
};

export type TiktokProfileScrapeRequest = {
  profiles: string[];
  max_items: number;
  get_followers: boolean;
  get_following: boolean;
  country: string;
  industry: string;
  project: string;
  save_to_database: boolean;
};

export type TiktokProfileScrapeRow = {
  id: number | string;
  url: string;
  username: string;
  nickname: string;
  bio?: string | null;
  bio_url?: string | null;
  followers: number;
  following: number;
  likes: number;
  videos: number;
  is_verified: boolean;
  profile_category?: string | null;
  avatar?: string | null;
  country: string;
  industry: string;
  project: string;
  last_updated: string;
};

export type TiktokPostScrapeRequest = {
  start_urls: string[];
  start_date: string;
  end_date: string;
  max_items: number;
  country: string;
  industry: string;
  project: string;
  save_to_database: boolean;
};

export type TiktokPostScrapeRow = {
  id?: string | number;
  url?: string | null;
  username?: string | null;
  caption?: string | null;
  text?: string | null;
  uploaded_at?: string | null;
  views?: number | null;
  comments?: number | null;
  likes?: number | null;
  shares?: number | null;
  country?: string | null;
  industry?: string | null;
  project?: string | null;
  last_updated?: string | null;
};

function getRowsFromResponse<TRow>(payload: unknown, responseKeys: string[]): TRow[] {
  if (Array.isArray(payload)) return payload as TRow[];

  if (payload && typeof payload === "object") {
    const data = payload as Record<string, unknown>;
    const candidates = [
      ...responseKeys.map((key) => data[key]),
      data.data,
      data.items,
      data.results,
      data.rows,
    ];
    const rows = candidates.find(Array.isArray);

    if (rows) return rows as TRow[];
  }

  return [];
}

export type InstagramProfileScrapeResult = {
  job_id?: string;
  status?: string;
  total?: number;
  completed?: number;
  successful?: number;
  failed?: number;
  progress_percent?: number;
  current_username?: string | null;
  save_to_database?: boolean;
  requested?: number;
  scraped?: number;
  saved_to_database?: boolean;
  profiles: InstagramProfileScrapeRow[];
  errors?: unknown[];
};

export type InstagramPostScrapeResult = {
  job_id?: string;
  status?: string;
  total?: number;
  completed?: number;
  successful?: number;
  failed?: number;
  progress_percent?: number;
  current_username?: string | null;
  scraped_posts?: number;
  save_to_database?: boolean;
  saved_to_database?: boolean;
  upload_images_to_s3?: boolean;
  images_uploaded?: number;
  images_skipped?: number;
  images_failed?: number;
  posts: InstagramPostScrapeRow[];
  errors?: unknown[];
};

export type TwitterProfileScrapeResult = {
  job_id?: string;
  status?: string;
  total?: number;
  completed?: number;
  successful?: number;
  failed?: number;
  progress_percent?: number;
  current_username?: string | null;
  save_to_database?: boolean;
  saved_to_database?: boolean;
  profiles: TwitterProfileScrapeRow[];
  errors?: unknown[];
};

export type TwitterPostScrapeResult = {
  job_id?: string;
  status?: string;
  total?: number;
  completed?: number;
  successful?: number;
  failed?: number;
  progress_percent?: number;
  current_username?: string | null;
  scraped_posts?: number;
  save_to_database?: boolean;
  saved_to_database?: boolean;
  posts: TwitterPostScrapeRow[];
  errors?: unknown[];
};

export type TwitterKeywordScrapeResult = {
  job_id?: string;
  status?: string;
  total?: number;
  completed?: number;
  successful?: number;
  failed?: number;
  progress_percent?: number;
  current_username?: string | null;
  current_keyword?: string | null;
  scraped_posts?: number;
  save_to_database?: boolean;
  saved_to_database?: boolean;
  posts: TwitterKeywordScrapeRow[];
  errors?: unknown[];
};

export type TiktokProfileScrapeResult = {
  job_id?: string;
  status?: string;
  total?: number;
  completed?: number;
  successful?: number;
  failed?: number;
  progress_percent?: number;
  current_profile?: string | null;
  save_to_database?: boolean;
  saved_to_database?: boolean;
  profiles: TiktokProfileScrapeRow[];
  errors?: unknown[];
};

export type TiktokPostScrapeResult = {
  job_id?: string;
  status?: string;
  total?: number;
  completed?: number;
  successful?: number;
  failed?: number;
  progress_percent?: number;
  current_url?: string | null;
  scraped_posts?: number;
  save_to_database?: boolean;
  saved_to_database?: boolean;
  posts: TiktokPostScrapeRow[];
  errors?: unknown[];
};

export type InstagramProfileJobStartResponse = {
  job_id: string;
  status: string;
  total: number;
  progress_url?: string;
};

export type InstagramPostJobStartResponse = InstagramProfileJobStartResponse;
export type LinkedinProfileJobStartResponse = InstagramProfileJobStartResponse;
export type LinkedinPostJobStartResponse = InstagramProfileJobStartResponse;
export type TwitterProfileJobStartResponse = InstagramProfileJobStartResponse;
export type TwitterPostJobStartResponse = InstagramProfileJobStartResponse;
export type TwitterKeywordJobStartResponse = InstagramProfileJobStartResponse;
export type TiktokProfileJobStartResponse = InstagramProfileJobStartResponse;
export type TiktokPostJobStartResponse = InstagramProfileJobStartResponse;

export type InstagramProfileJobProgress = Omit<InstagramProfileScrapeResult, "profiles"> & {
  job_id: string;
  status: string;
  total: number;
  progress_url?: string;
  profiles?: InstagramProfileScrapeRow[];
};

export type InstagramPostJobProgress = Omit<InstagramPostScrapeResult, "posts"> & {
  job_id: string;
  status: string;
  total: number;
  progress_url?: string;
  posts?: InstagramPostScrapeRow[];
};

export type LinkedinProfileScrapeResult = {
  job_id?: string;
  status?: string;
  total?: number;
  completed?: number;
  successful?: number;
  failed?: number;
  progress_percent?: number;
  current_profile_url?: string | null;
  save_to_database?: boolean;
  saved_to_database?: boolean;
  profiles: LinkedinProfileScrapeRow[];
  errors?: unknown[];
};

export type LinkedinProfileJobProgress = Omit<LinkedinProfileScrapeResult, "profiles"> & {
  job_id: string;
  status: string;
  total: number;
  progress_url?: string;
  profiles?: LinkedinProfileScrapeRow[];
};

export type LinkedinPostScrapeResult = {
  job_id?: string;
  status?: string;
  total?: number;
  completed?: number;
  successful?: number;
  failed?: number;
  progress_percent?: number;
  current_target_url?: string | null;
  scraped_posts?: number;
  save_to_database?: boolean;
  saved_to_database?: boolean;
  posts: LinkedinPostScrapeRow[];
  errors?: unknown[];
};

export type LinkedinPostJobProgress = Omit<LinkedinPostScrapeResult, "posts"> & {
  job_id: string;
  status: string;
  total: number;
  progress_url?: string;
  posts?: LinkedinPostScrapeRow[];
};

export type TwitterProfileJobProgress = Omit<TwitterProfileScrapeResult, "profiles"> & {
  job_id: string;
  status: string;
  total: number;
  progress_url?: string;
  profiles?: TwitterProfileScrapeRow[];
};

export type TwitterPostJobProgress = Omit<TwitterPostScrapeResult, "posts"> & {
  job_id: string;
  status: string;
  total: number;
  progress_url?: string;
  posts?: TwitterPostScrapeRow[];
};

export type TwitterKeywordJobProgress = Omit<TwitterKeywordScrapeResult, "posts"> & {
  job_id: string;
  status: string;
  total: number;
  progress_url?: string;
  posts?: TwitterKeywordScrapeRow[];
};

export type TiktokProfileJobProgress = Omit<TiktokProfileScrapeResult, "profiles"> & {
  job_id: string;
  status: string;
  total: number;
  progress_url?: string;
  profiles?: TiktokProfileScrapeRow[];
};

export type TiktokPostJobProgress = Omit<TiktokPostScrapeResult, "posts"> & {
  job_id: string;
  status: string;
  total: number;
  progress_url?: string;
  posts?: TiktokPostScrapeRow[];
};

const JOB_TERMINAL_STATUSES = new Set(["completed", "failed", "cancelled"]);

function sleep(ms: number) {
  return new Promise((resolve) => window.setTimeout(resolve, ms));
}

function resolveInstagramJobProgressUrl(
  start: InstagramProfileJobStartResponse,
  collection: "profiles" | "posts"
) {
  if (start.progress_url) return start.progress_url;
  if (start.job_id) return `/api/v1/data-scraping/instagram/${collection}/jobs/${start.job_id}`;

  throw new Error(`Instagram ${collection} collection did not return a job id`);
}

function resolveLinkedinJobProgressUrl(
  start: LinkedinProfileJobStartResponse,
  collection: "profiles" | "posts"
) {
  if (start.progress_url) return start.progress_url;
  if (start.job_id) return `/api/v1/data-scraping/linkedin/${collection}/jobs/${start.job_id}`;

  throw new Error(`LinkedIn ${collection} collection did not return a job id`);
}

function resolveTwitterJobProgressUrl(
  start: TwitterProfileJobStartResponse,
  collection: "profiles" | "posts" | "keywords"
) {
  if (start.progress_url) return start.progress_url;
  if (start.job_id) return `/api/v1/data-scraping/twitter/${collection}/jobs/${start.job_id}`;

  throw new Error(`Twitter ${collection} collection did not return a job id`);
}

function resolveTiktokJobProgressUrl(
  start: TiktokProfileJobStartResponse,
  collection: "profiles" | "posts"
) {
  if (start.progress_url) return start.progress_url;
  if (start.job_id) return `/api/v1/data-scraping/tiktok/${collection}/jobs/${start.job_id}`;

  throw new Error(`TikTok ${collection} collection did not return a job id`);
}

function toInstagramProfileResult(
  payload: unknown,
  fallbackSaveToDatabase: boolean
): InstagramProfileScrapeResult {
  const data = payload && typeof payload === "object" ? (payload as Record<string, unknown>) : {};

  return {
    job_id: typeof data.job_id === "string" ? data.job_id : undefined,
    status: typeof data.status === "string" ? data.status : undefined,
    total: typeof data.total === "number" ? data.total : undefined,
    completed: typeof data.completed === "number" ? data.completed : undefined,
    successful: typeof data.successful === "number" ? data.successful : undefined,
    failed: typeof data.failed === "number" ? data.failed : undefined,
    progress_percent: typeof data.progress_percent === "number" ? data.progress_percent : undefined,
    current_username: typeof data.current_username === "string" || data.current_username === null ? data.current_username : undefined,
    save_to_database: typeof data.save_to_database === "boolean" ? data.save_to_database : undefined,
    requested: typeof data.requested === "number" ? data.requested : undefined,
    scraped: typeof data.scraped === "number" ? data.scraped : undefined,
    saved_to_database: typeof data.save_to_database === "boolean"
      ? data.save_to_database
      : typeof data.saved_to_database === "boolean"
        ? data.saved_to_database
        : fallbackSaveToDatabase,
    profiles: getRowsFromResponse<InstagramProfileScrapeRow>(payload, ["profiles"]),
    errors: Array.isArray(data.errors) ? data.errors : undefined,
  };
}

function toInstagramPostResult(
  payload: unknown,
  fallbackSaveToDatabase: boolean
): InstagramPostScrapeResult {
  const data = payload && typeof payload === "object" ? (payload as Record<string, unknown>) : {};

  return {
    job_id: typeof data.job_id === "string" ? data.job_id : undefined,
    status: typeof data.status === "string" ? data.status : undefined,
    total: typeof data.total === "number" ? data.total : undefined,
    completed: typeof data.completed === "number" ? data.completed : undefined,
    successful: typeof data.successful === "number" ? data.successful : undefined,
    failed: typeof data.failed === "number" ? data.failed : undefined,
    progress_percent: typeof data.progress_percent === "number" ? data.progress_percent : undefined,
    current_username: typeof data.current_username === "string" || data.current_username === null ? data.current_username : undefined,
    scraped_posts: typeof data.scraped_posts === "number" ? data.scraped_posts : undefined,
    save_to_database: typeof data.save_to_database === "boolean" ? data.save_to_database : undefined,
    saved_to_database: typeof data.saved_to_database === "boolean"
      ? data.saved_to_database
      : typeof data.save_to_database === "boolean"
        ? data.save_to_database
        : fallbackSaveToDatabase,
    upload_images_to_s3: typeof data.upload_images_to_s3 === "boolean" ? data.upload_images_to_s3 : undefined,
    images_uploaded: typeof data.images_uploaded === "number" ? data.images_uploaded : undefined,
    images_skipped: typeof data.images_skipped === "number" ? data.images_skipped : undefined,
    images_failed: typeof data.images_failed === "number" ? data.images_failed : undefined,
    posts: getRowsFromResponse<InstagramPostScrapeRow>(payload, ["posts"]),
    errors: Array.isArray(data.errors) ? data.errors : undefined,
  };
}

function toLinkedinProfileResult(
  payload: unknown,
  fallbackSaveToDatabase: boolean
): LinkedinProfileScrapeResult {
  const data = payload && typeof payload === "object" ? (payload as Record<string, unknown>) : {};

  return {
    job_id: typeof data.job_id === "string" ? data.job_id : undefined,
    status: typeof data.status === "string" ? data.status : undefined,
    total: typeof data.total === "number" ? data.total : undefined,
    completed: typeof data.completed === "number" ? data.completed : undefined,
    successful: typeof data.successful === "number" ? data.successful : undefined,
    failed: typeof data.failed === "number" ? data.failed : undefined,
    progress_percent: typeof data.progress_percent === "number" ? data.progress_percent : undefined,
    current_profile_url: typeof data.current_profile_url === "string" || data.current_profile_url === null
      ? data.current_profile_url
      : undefined,
    save_to_database: typeof data.save_to_database === "boolean" ? data.save_to_database : undefined,
    saved_to_database: typeof data.saved_to_database === "boolean"
      ? data.saved_to_database
      : typeof data.save_to_database === "boolean"
        ? data.save_to_database
        : fallbackSaveToDatabase,
    profiles: getRowsFromResponse<LinkedinProfileScrapeRow>(payload, ["profiles"]),
    errors: Array.isArray(data.errors) ? data.errors : undefined,
  };
}

function toLinkedinPostResult(
  payload: unknown,
  fallbackSaveToDatabase: boolean
): LinkedinPostScrapeResult {
  const data = payload && typeof payload === "object" ? (payload as Record<string, unknown>) : {};

  return {
    job_id: typeof data.job_id === "string" ? data.job_id : undefined,
    status: typeof data.status === "string" ? data.status : undefined,
    total: typeof data.total === "number" ? data.total : undefined,
    completed: typeof data.completed === "number" ? data.completed : undefined,
    successful: typeof data.successful === "number" ? data.successful : undefined,
    failed: typeof data.failed === "number" ? data.failed : undefined,
    progress_percent: typeof data.progress_percent === "number" ? data.progress_percent : undefined,
    current_target_url: typeof data.current_target_url === "string" || data.current_target_url === null
      ? data.current_target_url
      : undefined,
    scraped_posts: typeof data.scraped_posts === "number" ? data.scraped_posts : undefined,
    save_to_database: typeof data.save_to_database === "boolean" ? data.save_to_database : undefined,
    saved_to_database: typeof data.saved_to_database === "boolean"
      ? data.saved_to_database
      : typeof data.save_to_database === "boolean"
        ? data.save_to_database
        : fallbackSaveToDatabase,
    posts: getRowsFromResponse<LinkedinPostScrapeRow>(payload, ["posts"]),
    errors: Array.isArray(data.errors) ? data.errors : undefined,
  };
}

function toTwitterProfileResult(
  payload: unknown,
  fallbackSaveToDatabase: boolean
): TwitterProfileScrapeResult {
  const data = payload && typeof payload === "object" ? (payload as Record<string, unknown>) : {};

  return {
    job_id: typeof data.job_id === "string" ? data.job_id : undefined,
    status: typeof data.status === "string" ? data.status : undefined,
    total: typeof data.total === "number" ? data.total : undefined,
    completed: typeof data.completed === "number" ? data.completed : undefined,
    successful: typeof data.successful === "number" ? data.successful : undefined,
    failed: typeof data.failed === "number" ? data.failed : undefined,
    progress_percent: typeof data.progress_percent === "number" ? data.progress_percent : undefined,
    current_username: typeof data.current_username === "string" || data.current_username === null ? data.current_username : undefined,
    save_to_database: typeof data.save_to_database === "boolean" ? data.save_to_database : undefined,
    saved_to_database: typeof data.saved_to_database === "boolean"
      ? data.saved_to_database
      : typeof data.save_to_database === "boolean"
        ? data.save_to_database
        : fallbackSaveToDatabase,
    profiles: getRowsFromResponse<TwitterProfileScrapeRow>(payload, ["profiles"]),
    errors: Array.isArray(data.errors) ? data.errors : undefined,
  };
}

function toTwitterPostResult(
  payload: unknown,
  fallbackSaveToDatabase: boolean
): TwitterPostScrapeResult {
  const data = payload && typeof payload === "object" ? (payload as Record<string, unknown>) : {};

  return {
    job_id: typeof data.job_id === "string" ? data.job_id : undefined,
    status: typeof data.status === "string" ? data.status : undefined,
    total: typeof data.total === "number" ? data.total : undefined,
    completed: typeof data.completed === "number" ? data.completed : undefined,
    successful: typeof data.successful === "number" ? data.successful : undefined,
    failed: typeof data.failed === "number" ? data.failed : undefined,
    progress_percent: typeof data.progress_percent === "number" ? data.progress_percent : undefined,
    current_username: typeof data.current_username === "string" || data.current_username === null ? data.current_username : undefined,
    scraped_posts: typeof data.scraped_posts === "number" ? data.scraped_posts : undefined,
    save_to_database: typeof data.save_to_database === "boolean" ? data.save_to_database : undefined,
    saved_to_database: typeof data.saved_to_database === "boolean"
      ? data.saved_to_database
      : typeof data.save_to_database === "boolean"
        ? data.save_to_database
        : fallbackSaveToDatabase,
    posts: getRowsFromResponse<TwitterPostScrapeRow>(payload, ["posts"]),
    errors: Array.isArray(data.errors) ? data.errors : undefined,
  };
}

function toTwitterKeywordResult(
  payload: unknown,
  fallbackSaveToDatabase: boolean
): TwitterKeywordScrapeResult {
  const data = payload && typeof payload === "object" ? (payload as Record<string, unknown>) : {};

  return {
    job_id: typeof data.job_id === "string" ? data.job_id : undefined,
    status: typeof data.status === "string" ? data.status : undefined,
    total: typeof data.total === "number" ? data.total : undefined,
    completed: typeof data.completed === "number" ? data.completed : undefined,
    successful: typeof data.successful === "number" ? data.successful : undefined,
    failed: typeof data.failed === "number" ? data.failed : undefined,
    progress_percent: typeof data.progress_percent === "number" ? data.progress_percent : undefined,
    current_username: typeof data.current_username === "string" || data.current_username === null ? data.current_username : undefined,
    current_keyword: typeof data.current_keyword === "string" || data.current_keyword === null ? data.current_keyword : undefined,
    scraped_posts: typeof data.scraped_posts === "number" ? data.scraped_posts : undefined,
    save_to_database: typeof data.save_to_database === "boolean" ? data.save_to_database : undefined,
    saved_to_database: typeof data.saved_to_database === "boolean"
      ? data.saved_to_database
      : typeof data.save_to_database === "boolean"
        ? data.save_to_database
        : fallbackSaveToDatabase,
    posts: getRowsFromResponse<TwitterKeywordScrapeRow>(payload, ["posts", "tweets"]),
    errors: Array.isArray(data.errors) ? data.errors : undefined,
  };
}

function toTiktokProfileResult(
  payload: unknown,
  fallbackSaveToDatabase: boolean
): TiktokProfileScrapeResult {
  const data = payload && typeof payload === "object" ? (payload as Record<string, unknown>) : {};

  return {
    job_id: typeof data.job_id === "string" ? data.job_id : undefined,
    status: typeof data.status === "string" ? data.status : undefined,
    total: typeof data.total === "number" ? data.total : undefined,
    completed: typeof data.completed === "number" ? data.completed : undefined,
    successful: typeof data.successful === "number" ? data.successful : undefined,
    failed: typeof data.failed === "number" ? data.failed : undefined,
    progress_percent: typeof data.progress_percent === "number" ? data.progress_percent : undefined,
    current_profile: typeof data.current_profile === "string" || data.current_profile === null ? data.current_profile : undefined,
    save_to_database: typeof data.save_to_database === "boolean" ? data.save_to_database : undefined,
    saved_to_database: typeof data.saved_to_database === "boolean"
      ? data.saved_to_database
      : typeof data.save_to_database === "boolean"
        ? data.save_to_database
        : fallbackSaveToDatabase,
    profiles: getRowsFromResponse<TiktokProfileScrapeRow>(payload, ["profiles"]),
    errors: Array.isArray(data.errors) ? data.errors : undefined,
  };
}

function toTiktokPostResult(
  payload: unknown,
  fallbackSaveToDatabase: boolean
): TiktokPostScrapeResult {
  const data = payload && typeof payload === "object" ? (payload as Record<string, unknown>) : {};

  return {
    job_id: typeof data.job_id === "string" ? data.job_id : undefined,
    status: typeof data.status === "string" ? data.status : undefined,
    total: typeof data.total === "number" ? data.total : undefined,
    completed: typeof data.completed === "number" ? data.completed : undefined,
    successful: typeof data.successful === "number" ? data.successful : undefined,
    failed: typeof data.failed === "number" ? data.failed : undefined,
    progress_percent: typeof data.progress_percent === "number" ? data.progress_percent : undefined,
    current_url: typeof data.current_url === "string" || data.current_url === null ? data.current_url : undefined,
    scraped_posts: typeof data.scraped_posts === "number" ? data.scraped_posts : undefined,
    save_to_database: typeof data.save_to_database === "boolean" ? data.save_to_database : undefined,
    saved_to_database: typeof data.saved_to_database === "boolean"
      ? data.saved_to_database
      : typeof data.save_to_database === "boolean"
        ? data.save_to_database
        : fallbackSaveToDatabase,
    posts: getRowsFromResponse<TiktokPostScrapeRow>(payload, ["posts", "videos"]),
    errors: Array.isArray(data.errors) ? data.errors : undefined,
  };
}

export async function startInstagramProfileJob(
  body: InstagramProfileScrapeRequest
): Promise<InstagramProfileJobStartResponse> {
  const jobBody = {
    usernames: body.usernames,
    country: body.country,
    industry: body.industry,
    project: body.project,
    save_to_database: body.save_to_database,
  };
  const res = await apiFetch("/api/v1/data-scraping/instagram/profiles/jobs", {
    method: "POST",
    body: JSON.stringify(jobBody),
  });

  if (!res.ok) {
    const errorText = await res.text().catch(() => "");
    throw new Error(errorText || "Failed to start Instagram profile collection job");
  }

  return res.json();
}

export async function startLinkedinProfileJob(
  body: LinkedinProfileScrapeRequest
): Promise<LinkedinProfileJobStartResponse> {
  const res = await apiFetch("/api/v1/data-scraping/linkedin/profiles/jobs", {
    method: "POST",
    body: JSON.stringify(body),
  });

  if (!res.ok) {
    const errorText = await res.text().catch(() => "");
    throw new Error(errorText || "Failed to start LinkedIn profile collection job");
  }

  return res.json();
}

export async function startLinkedinPostJob(
  body: LinkedinPostScrapeRequest
): Promise<LinkedinPostJobStartResponse> {
  const res = await apiFetch("/api/v1/data-scraping/linkedin/posts/jobs", {
    method: "POST",
    body: JSON.stringify(body),
  });

  if (!res.ok) {
    const errorText = await res.text().catch(() => "");
    throw new Error(errorText || "Failed to start LinkedIn posts collection job");
  }

  return res.json();
}

export async function startInstagramPostJob(
  body: InstagramPostScrapeRequest
): Promise<InstagramPostJobStartResponse> {
  const res = await apiFetch("/api/v1/data-scraping/instagram/posts/jobs", {
    method: "POST",
    body: JSON.stringify(body),
  });

  if (!res.ok) {
    const errorText = await res.text().catch(() => "");
    throw new Error(errorText || "Failed to start Instagram posts collection job");
  }

  return res.json();
}

export async function startTwitterProfileJob(
  body: TwitterProfileScrapeRequest
): Promise<TwitterProfileJobStartResponse> {
  const res = await apiFetch("/api/v1/data-scraping/twitter/profiles/jobs", {
    method: "POST",
    body: JSON.stringify(body),
  });

  if (!res.ok) {
    const errorText = await res.text().catch(() => "");
    throw new Error(errorText || "Failed to start Twitter profile collection job");
  }

  return res.json();
}

export async function startTwitterPostJob(
  body: TwitterPostScrapeRequest
): Promise<TwitterPostJobStartResponse> {
  const res = await apiFetch("/api/v1/data-scraping/twitter/posts/jobs", {
    method: "POST",
    body: JSON.stringify(body),
  });

  if (!res.ok) {
    const errorText = await res.text().catch(() => "");
    throw new Error(errorText || "Failed to start Twitter posts collection job");
  }

  return res.json();
}

export async function startTwitterKeywordJob(
  body: TwitterKeywordScrapeRequest
): Promise<TwitterKeywordJobStartResponse> {
  const res = await apiFetch("/api/v1/data-scraping/twitter/keywords/jobs", {
    method: "POST",
    body: JSON.stringify(body),
  });

  if (!res.ok) {
    const errorText = await res.text().catch(() => "");
    throw new Error(errorText || "Failed to start Twitter keyword collection job");
  }

  return res.json();
}

export async function startTiktokProfileJob(
  body: TiktokProfileScrapeRequest
): Promise<TiktokProfileJobStartResponse> {
  const res = await apiFetch("/api/v1/data-scraping/tiktok/profiles/jobs", {
    method: "POST",
    body: JSON.stringify(body),
  });

  if (!res.ok) {
    const errorText = await res.text().catch(() => "");
    throw new Error(errorText || "Failed to start TikTok profile collection job");
  }

  return res.json();
}

export async function startTiktokPostJob(
  body: TiktokPostScrapeRequest
): Promise<TiktokPostJobStartResponse> {
  const res = await apiFetch("/api/v1/data-scraping/tiktok/posts/jobs", {
    method: "POST",
    body: JSON.stringify(body),
  });

  if (!res.ok) {
    const errorText = await res.text().catch(() => "");
    throw new Error(errorText || "Failed to start TikTok posts collection job");
  }

  return res.json();
}

export async function getInstagramProfileJob(
  progressUrl: string,
  fallbackSaveToDatabase: boolean
): Promise<InstagramProfileJobProgress> {
  const res = await apiFetch(progressUrl);

  if (!res.ok) {
    const errorText = await res.text().catch(() => "");
    throw new Error(errorText || "Failed to fetch Instagram profile collection progress");
  }

  const payload = await res.json();
  const result = toInstagramProfileResult(payload, fallbackSaveToDatabase);

  return {
    ...result,
    job_id: result.job_id ?? "",
    status: result.status ?? "unknown",
    total: result.total ?? 0,
    profiles: result.profiles,
  };
}

export async function getLinkedinProfileJob(
  progressUrl: string,
  fallbackSaveToDatabase: boolean
): Promise<LinkedinProfileJobProgress> {
  const res = await apiFetch(progressUrl);

  if (!res.ok) {
    const errorText = await res.text().catch(() => "");
    throw new Error(errorText || "Failed to fetch LinkedIn profile collection progress");
  }

  const payload = await res.json();
  const result = toLinkedinProfileResult(payload, fallbackSaveToDatabase);

  return {
    ...result,
    job_id: result.job_id ?? "",
    status: result.status ?? "unknown",
    total: result.total ?? 0,
    profiles: result.profiles,
  };
}

export async function getLinkedinPostJob(
  progressUrl: string,
  fallbackSaveToDatabase: boolean
): Promise<LinkedinPostJobProgress> {
  const res = await apiFetch(progressUrl);

  if (!res.ok) {
    const errorText = await res.text().catch(() => "");
    throw new Error(errorText || "Failed to fetch LinkedIn posts collection progress");
  }

  const payload = await res.json();
  const result = toLinkedinPostResult(payload, fallbackSaveToDatabase);

  return {
    ...result,
    job_id: result.job_id ?? "",
    status: result.status ?? "unknown",
    total: result.total ?? 0,
    posts: result.posts,
  };
}

export async function getInstagramPostJob(
  progressUrl: string,
  fallbackSaveToDatabase: boolean
): Promise<InstagramPostJobProgress> {
  const res = await apiFetch(progressUrl);

  if (!res.ok) {
    const errorText = await res.text().catch(() => "");
    throw new Error(errorText || "Failed to fetch Instagram posts collection progress");
  }

  const payload = await res.json();
  const result = toInstagramPostResult(payload, fallbackSaveToDatabase);

  return {
    ...result,
    job_id: result.job_id ?? "",
    status: result.status ?? "unknown",
    total: result.total ?? 0,
    posts: result.posts,
  };
}

export async function getTwitterProfileJob(
  progressUrl: string,
  fallbackSaveToDatabase: boolean
): Promise<TwitterProfileJobProgress> {
  const res = await apiFetch(progressUrl);

  if (!res.ok) {
    const errorText = await res.text().catch(() => "");
    throw new Error(errorText || "Failed to fetch Twitter profile collection progress");
  }

  const payload = await res.json();
  const result = toTwitterProfileResult(payload, fallbackSaveToDatabase);

  return {
    ...result,
    job_id: result.job_id ?? "",
    status: result.status ?? "unknown",
    total: result.total ?? 0,
    profiles: result.profiles,
  };
}

export async function getTwitterPostJob(
  progressUrl: string,
  fallbackSaveToDatabase: boolean
): Promise<TwitterPostJobProgress> {
  const res = await apiFetch(progressUrl);

  if (!res.ok) {
    const errorText = await res.text().catch(() => "");
    throw new Error(errorText || "Failed to fetch Twitter posts collection progress");
  }

  const payload = await res.json();
  const result = toTwitterPostResult(payload, fallbackSaveToDatabase);

  return {
    ...result,
    job_id: result.job_id ?? "",
    status: result.status ?? "unknown",
    total: result.total ?? 0,
    posts: result.posts,
  };
}

export async function getTwitterKeywordJob(
  progressUrl: string,
  fallbackSaveToDatabase: boolean
): Promise<TwitterKeywordJobProgress> {
  const res = await apiFetch(progressUrl);

  if (!res.ok) {
    const errorText = await res.text().catch(() => "");
    throw new Error(errorText || "Failed to fetch Twitter keyword collection progress");
  }

  const payload = await res.json();
  const result = toTwitterKeywordResult(payload, fallbackSaveToDatabase);

  return {
    ...result,
    job_id: result.job_id ?? "",
    status: result.status ?? "unknown",
    total: result.total ?? 0,
    posts: result.posts,
  };
}

export async function getTiktokProfileJob(
  progressUrl: string,
  fallbackSaveToDatabase: boolean
): Promise<TiktokProfileJobProgress> {
  const res = await apiFetch(progressUrl);

  if (!res.ok) {
    const errorText = await res.text().catch(() => "");
    throw new Error(errorText || "Failed to fetch TikTok profile collection progress");
  }

  const payload = await res.json();
  const result = toTiktokProfileResult(payload, fallbackSaveToDatabase);

  return {
    ...result,
    job_id: result.job_id ?? "",
    status: result.status ?? "unknown",
    total: result.total ?? 0,
    profiles: result.profiles,
  };
}

export async function getTiktokPostJob(
  progressUrl: string,
  fallbackSaveToDatabase: boolean
): Promise<TiktokPostJobProgress> {
  const res = await apiFetch(progressUrl);

  if (!res.ok) {
    const errorText = await res.text().catch(() => "");
    throw new Error(errorText || "Failed to fetch TikTok posts collection progress");
  }

  const payload = await res.json();
  const result = toTiktokPostResult(payload, fallbackSaveToDatabase);

  return {
    ...result,
    job_id: result.job_id ?? "",
    status: result.status ?? "unknown",
    total: result.total ?? 0,
    posts: result.posts,
  };
}

export async function scrapeInstagramProfiles(
  body: InstagramProfileScrapeRequest,
  onProgress?: (progress: InstagramProfileJobProgress) => void
): Promise<InstagramProfileScrapeResult> {
  const start = await startInstagramProfileJob(body);
  const progressUrl = resolveInstagramJobProgressUrl(start, "profiles");
  onProgress?.({
    job_id: start.job_id,
    status: start.status,
    total: start.total,
    completed: 0,
    progress_percent: 0,
    saved_to_database: body.save_to_database,
    profiles: [],
    progress_url: progressUrl,
  });

  let progress: InstagramProfileJobProgress | null = null;

  for (let attempt = 0; attempt < 240; attempt += 1) {
    await sleep(attempt === 0 ? 500 : 1500);
    progress = await getInstagramProfileJob(progressUrl, body.save_to_database);
    onProgress?.(progress);

    if (JOB_TERMINAL_STATUSES.has(progress.status.toLowerCase())) {
      break;
    }
  }

  if (!progress) {
    throw new Error("Instagram profile collection did not return progress");
  }

  if (!JOB_TERMINAL_STATUSES.has(progress.status.toLowerCase())) {
    throw new Error("Instagram profile collection timed out");
  }

  if (progress.status.toLowerCase() !== "completed") {
    throw new Error(`Instagram profile collection ${progress.status}`);
  }

  return {
    ...progress,
    profiles: progress.profiles ?? [],
  };
}

export async function scrapeLinkedinProfiles(
  body: LinkedinProfileScrapeRequest,
  onProgress?: (progress: LinkedinProfileJobProgress) => void
): Promise<LinkedinProfileScrapeResult> {
  const start = await startLinkedinProfileJob(body);
  const progressUrl = resolveLinkedinJobProgressUrl(start, "profiles");
  onProgress?.({
    job_id: start.job_id,
    status: start.status,
    total: start.total,
    completed: 0,
    progress_percent: 0,
    saved_to_database: body.save_to_database,
    profiles: [],
    progress_url: progressUrl,
  });

  let progress: LinkedinProfileJobProgress | null = null;

  for (let attempt = 0; attempt < 240; attempt += 1) {
    await sleep(attempt === 0 ? 500 : 1500);
    progress = await getLinkedinProfileJob(progressUrl, body.save_to_database);
    onProgress?.(progress);

    if (JOB_TERMINAL_STATUSES.has(progress.status.toLowerCase())) break;
  }

  if (!progress) throw new Error("LinkedIn profile collection did not return progress");
  if (!JOB_TERMINAL_STATUSES.has(progress.status.toLowerCase())) {
    throw new Error("LinkedIn profile collection timed out");
  }
  if (progress.status.toLowerCase() !== "completed") {
    throw new Error(`LinkedIn profile collection ${progress.status}`);
  }

  return { ...progress, profiles: progress.profiles ?? [] };
}

export async function scrapeLinkedinPosts(
  body: LinkedinPostScrapeRequest,
  onProgress?: (progress: LinkedinPostJobProgress) => void
): Promise<LinkedinPostScrapeResult> {
  const start = await startLinkedinPostJob(body);
  const progressUrl = resolveLinkedinJobProgressUrl(start, "posts");
  onProgress?.({
    job_id: start.job_id,
    status: start.status,
    total: start.total,
    completed: 0,
    progress_percent: 0,
    scraped_posts: 0,
    saved_to_database: body.save_to_database,
    posts: [],
    progress_url: progressUrl,
  });

  let progress: LinkedinPostJobProgress | null = null;

  for (let attempt = 0; attempt < 240; attempt += 1) {
    await sleep(attempt === 0 ? 500 : 1500);
    progress = await getLinkedinPostJob(progressUrl, body.save_to_database);
    onProgress?.(progress);
    if (JOB_TERMINAL_STATUSES.has(progress.status.toLowerCase())) break;
  }

  if (!progress) throw new Error("LinkedIn posts collection did not return progress");
  if (!JOB_TERMINAL_STATUSES.has(progress.status.toLowerCase())) {
    throw new Error("LinkedIn posts collection timed out");
  }
  if (progress.status.toLowerCase() !== "completed") {
    throw new Error(`LinkedIn posts collection ${progress.status}`);
  }

  return { ...progress, posts: progress.posts ?? [] };
}

export async function scrapeInstagramPosts(
  body: InstagramPostScrapeRequest,
  onProgress?: (progress: InstagramPostJobProgress) => void
): Promise<InstagramPostScrapeResult> {
  const start = await startInstagramPostJob(body);
  const progressUrl = resolveInstagramJobProgressUrl(start, "posts");
  onProgress?.({
    job_id: start.job_id,
    status: start.status,
    total: start.total,
    completed: 0,
    progress_percent: 0,
    saved_to_database: body.save_to_database,
    upload_images_to_s3: body.upload_images_to_s3,
    posts: [],
    progress_url: progressUrl,
  });

  let progress: InstagramPostJobProgress | null = null;

  for (let attempt = 0; attempt < 240; attempt += 1) {
    await sleep(attempt === 0 ? 500 : 1500);
    progress = await getInstagramPostJob(progressUrl, body.save_to_database);
    onProgress?.(progress);

    if (JOB_TERMINAL_STATUSES.has(progress.status.toLowerCase())) {
      break;
    }
  }

  if (!progress) {
    throw new Error("Instagram posts collection did not return progress");
  }

  if (!JOB_TERMINAL_STATUSES.has(progress.status.toLowerCase())) {
    throw new Error("Instagram posts collection timed out");
  }

  if (progress.status.toLowerCase() !== "completed") {
    throw new Error(`Instagram posts collection ${progress.status}`);
  }

  return {
    ...progress,
    posts: progress.posts ?? [],
  };
}

export async function scrapeTwitterProfiles(
  body: TwitterProfileScrapeRequest,
  onProgress?: (progress: TwitterProfileJobProgress) => void
): Promise<TwitterProfileScrapeResult> {
  const start = await startTwitterProfileJob(body);
  const progressUrl = resolveTwitterJobProgressUrl(start, "profiles");
  onProgress?.({
    job_id: start.job_id,
    status: start.status,
    total: start.total,
    completed: 0,
    progress_percent: 0,
    saved_to_database: body.save_to_database,
    profiles: [],
    progress_url: progressUrl,
  });

  let progress: TwitterProfileJobProgress | null = null;

  for (let attempt = 0; attempt < 240; attempt += 1) {
    await sleep(attempt === 0 ? 500 : 1500);
    progress = await getTwitterProfileJob(progressUrl, body.save_to_database);
    onProgress?.(progress);

    if (JOB_TERMINAL_STATUSES.has(progress.status.toLowerCase())) {
      break;
    }
  }

  if (!progress) {
    throw new Error("Twitter profile collection did not return progress");
  }

  if (!JOB_TERMINAL_STATUSES.has(progress.status.toLowerCase())) {
    throw new Error("Twitter profile collection timed out");
  }

  if (progress.status.toLowerCase() !== "completed") {
    throw new Error(`Twitter profile collection ${progress.status}`);
  }

  return {
    ...progress,
    profiles: progress.profiles ?? [],
  };
}

export async function scrapeTwitterPosts(
  body: TwitterPostScrapeRequest,
  onProgress?: (progress: TwitterPostJobProgress) => void
): Promise<TwitterPostScrapeResult> {
  const start = await startTwitterPostJob(body);
  const progressUrl = resolveTwitterJobProgressUrl(start, "posts");
  onProgress?.({
    job_id: start.job_id,
    status: start.status,
    total: start.total,
    completed: 0,
    progress_percent: 0,
    saved_to_database: body.save_to_database,
    posts: [],
    progress_url: progressUrl,
  });

  let progress: TwitterPostJobProgress | null = null;

  for (let attempt = 0; attempt < 240; attempt += 1) {
    await sleep(attempt === 0 ? 500 : 1500);
    progress = await getTwitterPostJob(progressUrl, body.save_to_database);
    onProgress?.(progress);

    if (JOB_TERMINAL_STATUSES.has(progress.status.toLowerCase())) {
      break;
    }
  }

  if (!progress) {
    throw new Error("Twitter posts collection did not return progress");
  }

  if (!JOB_TERMINAL_STATUSES.has(progress.status.toLowerCase())) {
    throw new Error("Twitter posts collection timed out");
  }

  if (progress.status.toLowerCase() !== "completed") {
    throw new Error(`Twitter posts collection ${progress.status}`);
  }

  return {
    ...progress,
    posts: progress.posts ?? [],
  };
}

export async function scrapeTwitterKeywords(
  body: TwitterKeywordScrapeRequest,
  onProgress?: (progress: TwitterKeywordJobProgress) => void
): Promise<TwitterKeywordScrapeResult> {
  const start = await startTwitterKeywordJob(body);
  const progressUrl = resolveTwitterJobProgressUrl(start, "keywords");
  onProgress?.({
    job_id: start.job_id,
    status: start.status,
    total: start.total,
    completed: 0,
    progress_percent: 0,
    saved_to_database: body.save_to_database,
    posts: [],
    progress_url: progressUrl,
  });

  let progress: TwitterKeywordJobProgress | null = null;

  for (let attempt = 0; attempt < 240; attempt += 1) {
    await sleep(attempt === 0 ? 500 : 1500);
    progress = await getTwitterKeywordJob(progressUrl, body.save_to_database);
    onProgress?.(progress);

    if (JOB_TERMINAL_STATUSES.has(progress.status.toLowerCase())) {
      break;
    }
  }

  if (!progress) {
    throw new Error("Twitter keyword collection did not return progress");
  }

  if (!JOB_TERMINAL_STATUSES.has(progress.status.toLowerCase())) {
    throw new Error("Twitter keyword collection timed out");
  }

  if (progress.status.toLowerCase() !== "completed") {
    throw new Error(`Twitter keyword collection ${progress.status}`);
  }

  return {
    ...progress,
    posts: progress.posts ?? [],
  };
}

export async function scrapeTiktokProfiles(
  body: TiktokProfileScrapeRequest,
  onProgress?: (progress: TiktokProfileJobProgress) => void
): Promise<TiktokProfileScrapeResult> {
  const start = await startTiktokProfileJob(body);
  const progressUrl = resolveTiktokJobProgressUrl(start, "profiles");
  onProgress?.({
    job_id: start.job_id,
    status: start.status,
    total: start.total,
    completed: 0,
    progress_percent: 0,
    saved_to_database: body.save_to_database,
    profiles: [],
    progress_url: progressUrl,
  });

  let progress: TiktokProfileJobProgress | null = null;

  for (let attempt = 0; attempt < 240; attempt += 1) {
    await sleep(attempt === 0 ? 500 : 1500);
    progress = await getTiktokProfileJob(progressUrl, body.save_to_database);
    onProgress?.(progress);

    if (JOB_TERMINAL_STATUSES.has(progress.status.toLowerCase())) {
      break;
    }
  }

  if (!progress) {
    throw new Error("TikTok profile collection did not return progress");
  }

  if (!JOB_TERMINAL_STATUSES.has(progress.status.toLowerCase())) {
    throw new Error("TikTok profile collection timed out");
  }

  if (progress.status.toLowerCase() !== "completed") {
    throw new Error(`TikTok profile collection ${progress.status}`);
  }

  return {
    ...progress,
    profiles: progress.profiles ?? [],
  };
}

export async function scrapeTiktokPosts(
  body: TiktokPostScrapeRequest,
  onProgress?: (progress: TiktokPostJobProgress) => void
): Promise<TiktokPostScrapeResult> {
  const start = await startTiktokPostJob(body);
  const progressUrl = resolveTiktokJobProgressUrl(start, "posts");
  onProgress?.({
    job_id: start.job_id,
    status: start.status,
    total: start.total,
    completed: 0,
    progress_percent: 0,
    saved_to_database: body.save_to_database,
    posts: [],
    progress_url: progressUrl,
  });

  let progress: TiktokPostJobProgress | null = null;

  for (let attempt = 0; attempt < 240; attempt += 1) {
    await sleep(attempt === 0 ? 500 : 1500);
    progress = await getTiktokPostJob(progressUrl, body.save_to_database);
    onProgress?.(progress);

    if (JOB_TERMINAL_STATUSES.has(progress.status.toLowerCase())) {
      break;
    }
  }

  if (!progress) {
    throw new Error("TikTok posts collection did not return progress");
  }

  if (!JOB_TERMINAL_STATUSES.has(progress.status.toLowerCase())) {
    throw new Error("TikTok posts collection timed out");
  }

  if (progress.status.toLowerCase() !== "completed") {
    throw new Error(`TikTok posts collection ${progress.status}`);
  }

  return {
    ...progress,
    posts: progress.posts ?? [],
  };
}
