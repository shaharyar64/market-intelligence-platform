"use client";

import { useMemo, useState } from "react";
import {
  AtSign,
  Clock3,
  DatabaseZap,
  FileSpreadsheet,
  Hash,
  Linkedin,
  Loader2,
  Play,
  Plus,
  RefreshCw,
  ShieldCheck,
  UploadCloud,
  X,
} from "lucide-react";
import DashboardTopbar from "@/components/layout/DashboardTopbar";
import ExportExcelButton from "@/components/ui/ExportExcelButton";
import {
  scrapeInstagramPosts,
  scrapeInstagramProfiles,
  scrapeLinkedinProfiles,
  scrapeLinkedinPosts,
  scrapeTiktokPosts,
  scrapeTiktokProfiles,
  scrapeTwitterKeywords,
  scrapeTwitterPosts,
  scrapeTwitterProfiles,
  type InstagramPostJobProgress,
  type InstagramProfileJobProgress,
  type LinkedinProfileJobProgress,
  type LinkedinProfileScrapeRow,
  type LinkedinPostJobProgress,
  type LinkedinPostScrapeRow,
  type TiktokPostJobProgress,
  type TiktokProfileJobProgress,
  type TwitterKeywordJobProgress,
  type TwitterProfileJobProgress,
  type TwitterPostJobProgress,
} from "@/lib/dataScraping";

export type PlatformKey = "instagram" | "linkedin" | "twitter" | "tiktok";
type CollectionStatus = "idle" | "running" | "ready" | "pushed";

type PlatformConfig = {
  key: PlatformKey;
  label: string;
  headline: string;
  hint: string;
  icon: typeof AtSign;
  accent: string;
  soft: string;
};

type InstagramProfileRow = {
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

type InstagramPostRow = {
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

type TwitterProfileRow = {
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

type TwitterPostRow = {
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

type TwitterKeywordRow = TwitterPostRow & {
  keyword?: string | null;
  query?: string | null;
  country?: string | null;
  industry?: string | null;
  project?: string | null;
  lang?: string | null;
  location_query?: string | null;
};

type TiktokProfileRow = {
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

type TiktokPostRow = {
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

const PLATFORM_CONFIG: Record<PlatformKey, PlatformConfig> = {
  instagram: {
    key: "instagram",
    label: "Instagram",
    headline: "Instagram Data Collection",
    hint: "Collect profiles, posts, reels, followers, comments, and engagement signals.",
    icon: AtSign,
    accent: "#e1306c",
    soft: "rgba(225,48,108,0.16)",
  },
  linkedin: {
    key: "linkedin",
    label: "LinkedIn",
    headline: "LinkedIn Data Collection",
    hint: "Collect company page posts, reactions, comments, followers, and engagement.",
    icon: Linkedin,
    accent: "#0a66c2",
    soft: "rgba(10,102,194,0.16)",
  },
  twitter: {
    key: "twitter",
    label: "Twitter",
    headline: "Twitter Data Collection",
    hint: "Collect handles, tweets, replies, reposts, impressions, and engagement.",
    icon: Hash,
    accent: "#111827",
    soft: "rgba(17,24,39,0.13)",
  },
  tiktok: {
    key: "tiktok",
    label: "TikTok",
    headline: "TikTok Data Collection",
    hint: "Collect creators, videos, views, comments, shares, and engagement signals.",
    icon: Play,
    accent: "#14b8a6",
    soft: "rgba(20,184,166,0.16)",
  },
};

type InstagramInputs = {
  usernames: string;
  country: string;
  industry: string;
  project: string;
};

type TwitterInputs = {
  usernames: string;
  country: string;
  industry: string;
  project: string;
};

type InstagramPostSettings = {
  startDate: string;
  endDate: string;
  uploadImagesToS3: boolean;
};

type TwitterPostSettings = {
  startDate: string;
  endDate: string;
};

type TwitterKeywordInputs = {
  keywords: string;
  lang: string;
  locationQuery: string;
  countryFilterTerms: string;
};

type TwitterKeywordSettings = {
  startDate: string;
  endDate: string;
  queryType: "Latest" | "Top";
  filterByCountry: boolean;
  excludeRetweets: boolean;
  excludeReplies: boolean;
  windowDays: number;
  maxPagesPerWindow: string;
};

type TiktokInputs = {
  profiles: string;
  country: string;
  industry: string;
  project: string;
};

type TiktokProfileSettings = {
  maxItems: number;
  getFollowers: boolean;
  getFollowing: boolean;
};

type TiktokPostSettings = {
  maxItems: number;
  startDate: string;
  endDate: string;
};

type LinkedinPostSettings = {
  startDate: string;
  endDate: string;
  maxPosts: number;
};

type JobProgressLike = {
  job_id?: string;
  status?: string;
  total?: number;
  completed?: number;
  successful?: number;
  failed?: number;
  progress_percent?: number;
  current_username?: string | null;
  current_keyword?: string | null;
  current_profile?: string | null;
  current_profile_url?: string | null;
  current_target_url?: string | null;
  current_url?: string | null;
  scraped_posts?: number;
  images_uploaded?: number;
  images_skipped?: number;
  images_failed?: number;
};

function parseUsernames(value: string) {
  return value
    .split(/[\n,]+/)
    .map((item) => item.trim().replace(/^@/, ""))
    .filter(Boolean);
}

function parseListValues(value: string) {
  return value
    .split(/[\n,]+/)
    .map((item) => item.trim())
    .filter(Boolean);
}

function formatNumber(value: number) {
  return new Intl.NumberFormat("en-US").format(value);
}

function getTodayDateInputValue() {
  return new Date().toLocaleDateString("en-CA");
}

function StatusPill({ status }: { status: CollectionStatus }) {
  const copy = {
    idle: "Ready to run",
    running: "Collecting",
    ready: "Ready to review",
    pushed: "Pushed to DB",
  }[status];

  return (
    <span className="inline-flex h-8 items-center gap-2 rounded-full border border-white/50 bg-white/55 px-3 text-xs font-bold shadow-sm backdrop-blur-xl">
      {status === "running" ? (
        <Loader2 className="h-3.5 w-3.5 animate-spin text-blue-600" />
      ) : status === "pushed" ? (
        <ShieldCheck className="h-3.5 w-3.5 text-emerald-600" />
      ) : (
        <Clock3 className="h-3.5 w-3.5 text-slate-500" />
      )}
      <span style={{ color: "var(--body-tx)" }}>{copy}</span>
    </span>
  );
}

function InstagramCollectionPage() {
  const platform = PLATFORM_CONFIG.instagram;
  const [inputs, setInputs] = useState<InstagramInputs>({
    usernames: "",
    country: "",
    industry: "",
    project: "",
  });
  const [profileStatus, setProfileStatus] = useState<CollectionStatus>("idle");
  const [postStatus, setPostStatus] = useState<CollectionStatus>("idle");
  const [activeCollection, setActiveCollection] = useState<"profile" | "posts">("profile");
  const [accountDraft, setAccountDraft] = useState("");
  const [postSettings, setPostSettings] = useState<InstagramPostSettings>({
    startDate: "2025-01-01",
    endDate: getTodayDateInputValue(),
    uploadImagesToS3: true,
  });
  const [profileRows, setProfileRows] = useState<InstagramProfileRow[]>([]);
  const [postRows, setPostRows] = useState<InstagramPostRow[]>([]);
  const [profileError, setProfileError] = useState<string | null>(null);
  const [postError, setPostError] = useState<string | null>(null);
  const [saveProfilesToDatabase, setSaveProfilesToDatabase] = useState(true);
  const [savePostsToDatabase, setSavePostsToDatabase] = useState(true);
  const [showProfileSaveConfirm, setShowProfileSaveConfirm] = useState(false);
  const [showPostSaveConfirm, setShowPostSaveConfirm] = useState(false);
  const [profileProgress, setProfileProgress] = useState<InstagramProfileJobProgress | null>(null);
  const [postProgress, setPostProgress] = useState<InstagramPostJobProgress | null>(null);

  const usernames = useMemo(() => parseUsernames(inputs.usernames), [inputs.usernames]);
  const usernameCount = usernames.length;
  const canRunProfile = Boolean(usernameCount > 0 && inputs.country.trim() && inputs.industry.trim() && inputs.project.trim());
  const postDateError =
    postSettings.startDate && postSettings.endDate && postSettings.endDate < postSettings.startDate
      ? "End date must be on or after start date."
      : null;
  const canRunPosts = Boolean(
    usernameCount > 0 &&
      postSettings.startDate &&
      postSettings.endDate &&
      !postDateError
  );
  const canRun = canRunProfile || canRunPosts;

  const executeProfileCollection = async (saveToDatabase = saveProfilesToDatabase) => {
    setProfileStatus("running");
    setProfileError(null);
    setProfileProgress(null);

    try {
      const result = await scrapeInstagramProfiles(
        {
          usernames,
          include_about_section: false,
          country: inputs.country,
          industry: inputs.industry,
          project: inputs.project,
          save_to_database: saveToDatabase,
        },
        (progress) => {
          setProfileProgress(progress);
          if (progress.profiles?.length) {
            setProfileRows(progress.profiles);
          }
        }
      );

      setProfileRows(result.profiles);
      setProfileStatus(result.saved_to_database ? "pushed" : "ready");
    } catch (error) {
      setProfileStatus("idle");
      setProfileError(error instanceof Error ? error.message : "Failed to collect Instagram profiles");
    }
  };

  const runProfileCollection = () => {
    if (!canRunProfile || profileStatus === "running") return;

    if (saveProfilesToDatabase) {
      setShowProfileSaveConfirm(true);
      return;
    }

    void executeProfileCollection(false);
  };

  const executePostCollection = async (saveToDatabase = savePostsToDatabase) => {
    if (postDateError) {
      setPostError(postDateError);
      return;
    }

    setPostStatus("running");
    setPostError(null);
    setPostProgress(null);

    try {
      const result = await scrapeInstagramPosts(
        {
          usernames,
          start_date: postSettings.startDate,
          end_date: postSettings.endDate,
          save_to_database: saveToDatabase,
          upload_images_to_s3: postSettings.uploadImagesToS3,
        },
        (progress) => {
          setPostProgress(progress);
          if (progress.posts?.length) {
            setPostRows(progress.posts);
          }
        }
      );

      setPostRows(result.posts);
      setPostStatus(result.saved_to_database ? "pushed" : "ready");
    } catch (error) {
      setPostStatus("idle");
      setPostError(error instanceof Error ? error.message : "Failed to collect Instagram posts");
    }
  };

  const runPostCollection = () => {
    if (postDateError) {
      setPostError(postDateError);
      return;
    }

    if (!canRunPosts || postStatus === "running") return;

    if (savePostsToDatabase) {
      setShowPostSaveConfirm(true);
      return;
    }

    void executePostCollection(false);
  };

  const resetProfile = () => {
    setProfileRows([]);
    setProfileStatus("idle");
    setProfileError(null);
    setProfileProgress(null);
  };

  const resetPosts = () => {
    setPostRows([]);
    setPostStatus("idle");
    setPostError(null);
    setPostProgress(null);
  };

  const updateInput = (key: keyof InstagramInputs, value: string) => {
    setInputs((current) => ({ ...current, [key]: value }));
    if (profileStatus !== "running") setProfileStatus(profileRows.length ? "ready" : "idle");
    if (postStatus !== "running") setPostStatus(postRows.length ? "ready" : "idle");
  };

  const updateUsernames = (nextUsernames: string[]) => {
    const unique = Array.from(new Set(parseUsernames(nextUsernames.join("\n"))));
    updateInput("usernames", unique.join("\n"));
  };

  const addDraftUsernames = (value = accountDraft) => {
    const next = parseUsernames(value);
    if (!next.length) return;
    updateUsernames([...usernames, ...next]);
    setAccountDraft("");
  };

  const removeUsername = (username: string) => {
    updateUsernames(usernames.filter((item) => item !== username));
  };

  return (
    <main className="min-h-screen">
      <DashboardTopbar title="Internal Data Collection" />

      <div className="space-y-6 p-8">
        <section
          className="overflow-hidden rounded-2xl border p-6 shadow-xl backdrop-blur-xl"
          style={{
            borderColor: "rgba(225,48,108,0.16)",
            background:
              "linear-gradient(135deg, rgba(255,255,255,0.92), rgba(255,242,248,0.8) 42%, rgba(239,246,255,0.88))",
          }}
        >
          <div className="flex flex-wrap items-center justify-between gap-6">
            <div className="flex min-w-0 items-start gap-4">
              <div className="flex h-14 w-14 shrink-0 items-center justify-center rounded-2xl bg-gradient-to-br from-pink-500 via-fuchsia-500 to-orange-400 text-white shadow-xl shadow-pink-500/20">
                <AtSign className="h-7 w-7" />
              </div>
              <div className="min-w-0">
                <div className="inline-flex rounded-full bg-white/70 px-3 py-1 text-xs font-black uppercase tracking-[0.18em] text-pink-600 shadow-sm">
                  Instagram Workspace
                </div>
                <h1 className="mt-3 text-3xl font-black tracking-tight" style={{ color: "var(--title-tx)" }}>
                  Collection Studio
                </h1>
                <p className="mt-2 max-w-3xl text-sm leading-6" style={{ color: "var(--muted-tx)" }}>
                  Use one shared batch setup, then run profile and posts collection as separate reviewable outputs.
                </p>
              </div>
            </div>

            <div className="grid min-w-[420px] gap-3 sm:grid-cols-3">
              {[
                ["Accounts", usernameCount, "from input"],
                ["Profiles", profileRows.length, "ready rows"],
                ["Posts", postRows.length, "ready rows"],
              ].map(([label, value, caption]) => (
                <div
                  key={label}
                  className="rounded-2xl border bg-white/70 px-5 py-4 shadow-sm backdrop-blur-xl"
                  style={{ borderColor: "var(--card-bd)" }}
                >
                  <div className="text-[10px] font-black uppercase tracking-wider" style={{ color: "var(--muted-tx)" }}>
                    {label}
                  </div>
                  <div className="mt-1 text-3xl font-black tracking-tight" style={{ color: "var(--title-tx)" }}>
                    {value}
                  </div>
                  <div className="mt-1 text-[11px] font-bold text-pink-600">{caption}</div>
                </div>
              ))}
            </div>
          </div>
        </section>

        <section
          className="rounded-2xl border bg-white/78 p-5 shadow-lg backdrop-blur-xl dark:bg-slate-900/78"
          style={{ borderColor: "var(--card-bd)" }}
        >
          <div className="grid gap-5 xl:grid-cols-[minmax(420px,1.05fr)_0.95fr]">
            <div
              className="rounded-2xl border p-5 shadow-sm"
              style={{
                borderColor: "rgba(225,48,108,0.16)",
                background: "linear-gradient(135deg, rgba(255,255,255,0.9), rgba(253,242,248,0.64))",
              }}
            >
              <div className="flex flex-wrap items-start justify-between gap-4">
                <div>
                  <h2 className="text-2xl font-black tracking-tight" style={{ color: "var(--title-tx)" }}>
                    Batch Setup
                  </h2>
                  <p className="mt-1 text-sm leading-6" style={{ color: "var(--muted-tx)" }}>
                    Add Instagram usernames once, then use the same batch for profile and posts collection.
                  </p>
                </div>
                <span
                  className="inline-flex h-9 items-center rounded-full px-4 text-xs font-black uppercase tracking-wider text-white shadow-lg"
                  style={{ background: canRun ? "#10b981" : "#94a3b8" }}
                >
                  {canRun ? "Ready" : "Needs input"}
                </span>
              </div>

              <div className="mt-5 rounded-2xl border bg-white/76 p-4 shadow-inner dark:bg-slate-950/25" style={{ borderColor: "var(--card-bd)" }}>
                <div className="flex items-center justify-between gap-4">
                  <label className="inline-flex items-center gap-2 text-xs font-black uppercase tracking-[0.18em] text-pink-600">
                    <AtSign className="h-4 w-4" />
                    Source Accounts
                  </label>
                  {usernameCount > 0 ? (
                    <button
                      type="button"
                      onClick={() => updateUsernames([])}
                      className="rounded-full bg-slate-100 px-3 py-1 text-xs font-black text-slate-500 transition hover:bg-slate-200"
                    >
                      Clear all
                    </button>
                  ) : (
                    <span className="rounded-full bg-pink-500/10 px-3 py-1 text-xs font-black text-pink-600">Empty</span>
                  )}
                </div>

                <div className="mt-4 flex gap-3">
                  <div className="flex min-w-0 flex-1 items-center rounded-xl border bg-white/82 px-4 shadow-sm focus-within:border-pink-400 focus-within:ring-4 focus-within:ring-pink-500/10 dark:bg-slate-900/40" style={{ borderColor: "var(--card-bd)" }}>
                    <span className="mr-1 text-lg font-black text-pink-500">@</span>
                    <input
                      value={accountDraft}
                      onChange={(event) => setAccountDraft(event.target.value)}
                      onKeyDown={(event) => {
                        if (event.key === "Enter" || event.key === ",") {
                          event.preventDefault();
                          addDraftUsernames();
                        }
                      }}
                      onPaste={(event) => {
                        const pasted = event.clipboardData.getData("text");
                        if (/[\n,]/.test(pasted)) {
                          event.preventDefault();
                          addDraftUsernames(`${accountDraft}\n${pasted}`);
                        }
                      }}
                      placeholder="type username and press Enter"
                      className="h-12 min-w-0 flex-1 border-0 bg-transparent text-sm font-black outline-none placeholder:text-slate-400"
                      style={{ color: "var(--title-tx)" }}
                    />
                  </div>
                  <button
                    type="button"
                    onClick={() => addDraftUsernames()}
                    disabled={!parseUsernames(accountDraft).length}
                    className="inline-flex h-12 items-center gap-2 rounded-xl bg-pink-500 px-5 text-sm font-black text-white shadow-lg shadow-pink-500/20 transition hover:bg-pink-600 disabled:cursor-not-allowed disabled:opacity-45"
                  >
                    <Plus className="h-4 w-4" />
                    Add
                  </button>
                </div>

                <div className="mt-4 min-h-36 rounded-xl border border-dashed bg-white/54 p-3 dark:bg-slate-900/25" style={{ borderColor: "rgba(225,48,108,0.22)" }}>
                  {usernames.length ? (
                    <div className="flex flex-wrap gap-2">
                      {usernames.map((username) => (
                        <span
                          key={username}
                          className="inline-flex h-9 items-center gap-2 rounded-full border bg-white px-3 text-sm font-black shadow-sm dark:bg-slate-900/60"
                          style={{ borderColor: "var(--card-bd)", color: "var(--title-tx)" }}
                        >
                          @{username}
                          <button
                            type="button"
                            onClick={() => removeUsername(username)}
                            className="inline-flex h-5 w-5 items-center justify-center rounded-full bg-slate-100 text-slate-500 transition hover:bg-pink-100 hover:text-pink-600 dark:bg-slate-800"
                            aria-label={`Remove ${username}`}
                          >
                            <X className="h-3.5 w-3.5" />
                          </button>
                        </span>
                      ))}
                    </div>
                  ) : (
                    <div className="flex h-28 items-center justify-center rounded-lg text-center text-sm font-bold" style={{ color: "var(--muted-tx)" }}>
                      Add usernames one by one, or paste a comma-separated list.
                    </div>
                  )}
                </div>

                <div className="mt-3 rounded-xl bg-slate-100/70 px-3 py-2 text-xs font-bold dark:bg-slate-800/40" style={{ color: "var(--muted-tx)" }}>
                  Profile and posts collection will use this same username list.
                </div>
              </div>
            </div>

            <div
              className="rounded-2xl border bg-white/72 p-5 shadow-sm backdrop-blur-xl dark:bg-slate-950/30"
              style={{ borderColor: "var(--card-bd)" }}
            >
              <div className="flex items-center justify-between gap-4">
                <div>
                  <div className="text-xs font-black uppercase tracking-[0.22em]" style={{ color: "var(--muted-tx)" }}>
                    Batch Details
                  </div>
                  <h3 className="mt-1 text-xl font-black tracking-tight" style={{ color: "var(--title-tx)" }}>
                    Output Metadata
                  </h3>
                </div>
                <div className="flex h-11 w-11 items-center justify-center rounded-xl bg-slate-900 text-white shadow-lg shadow-slate-900/15 dark:bg-white dark:text-slate-950">
                  <FileSpreadsheet className="h-5 w-5" />
                </div>
              </div>

              <div className="mt-5 grid gap-3">
              {([
                ["country", "Country", "SA"],
                ["industry", "Industry", "Banking"],
                ["project", "Project", "Internal Data Collection"],
              ] as const).map(([key, label, placeholder]) => (
                <label
                  key={key}
                  className="block rounded-2xl border bg-white/68 px-4 py-3 focus-within:border-pink-400 focus-within:ring-4 focus-within:ring-pink-500/10 dark:bg-slate-900/35"
                  style={{ borderColor: "var(--card-bd)" }}
                >
                  <span className="text-[10px] font-black uppercase tracking-wider" style={{ color: "var(--muted-tx)" }}>
                    {label}
                  </span>
                  <input
                    value={inputs[key]}
                    onChange={(event) => updateInput(key, event.target.value)}
                    placeholder={placeholder}
                    className="mt-1 h-8 w-full border-0 bg-transparent p-0 text-base font-black outline-none"
                    style={{ color: "var(--title-tx)" }}
                  />
                </label>
              ))}
              </div>

              <div className="mt-4 rounded-2xl border bg-gradient-to-r from-pink-500/10 to-orange-400/10 px-4 py-3" style={{ borderColor: "rgba(225,48,108,0.12)" }}>
                <div className="text-xs font-bold leading-5" style={{ color: "var(--muted-tx)" }}>
                  These values are attached to every exported row and will be sent with the approved database push.
                </div>
              </div>
            </div>
          </div>
        </section>

        <section
          className="rounded-2xl border bg-white/70 p-4 shadow-lg backdrop-blur-xl dark:bg-slate-900/70"
          style={{ borderColor: "var(--card-bd)" }}
        >
          <div className="mb-4 inline-flex rounded-2xl border bg-white/72 p-1 shadow-sm dark:bg-slate-950/35" style={{ borderColor: "var(--card-bd)" }}>
            {[
              {
                key: "profile" as const,
                label: "Profile Data",
                count: profileRows.length,
                accent: platform.accent,
              },
              {
                key: "posts" as const,
                label: "Posts Data",
                count: postRows.length,
                accent: "#8b5cf6",
              },
            ].map((tab) => {
              const selected = activeCollection === tab.key;

              return (
                <button
                  key={tab.key}
                  type="button"
                  onClick={() => setActiveCollection(tab.key)}
                  className="inline-flex h-11 items-center gap-3 rounded-xl px-4 text-sm font-black transition"
                  style={{
                    background: selected ? tab.accent : "transparent",
                    color: selected ? "#ffffff" : "var(--muted-tx)",
                    boxShadow: selected ? `0 12px 26px ${tab.key === "profile" ? platform.soft : "rgba(139,92,246,0.18)"}` : "none",
                  }}
                >
                  {tab.label}
                  <span
                    className="inline-flex min-w-7 justify-center rounded-full px-2 py-0.5 text-xs"
                    style={{
                      background: selected ? "rgba(255,255,255,0.22)" : "rgba(100,116,139,0.12)",
                      color: selected ? "#ffffff" : "var(--body-tx)",
                    }}
                  >
                    {tab.count}
                  </span>
                </button>
              );
            })}
          </div>

          {activeCollection === "profile" ? (
            <InstagramSection
              accent={platform.accent}
              soft={platform.soft}
              title="Profile Data"
              description="Account metadata, followers, verification, bio, country, industry, and project."
              usernameCount={usernameCount}
              rows={profileRows}
              status={profileStatus}
              canRun={canRunProfile}
              filename="instagram_profile_data_collection"
              sheetName="Instagram Profiles"
              onRun={runProfileCollection}
              onReset={resetProfile}
              onPush={() => setProfileStatus("pushed")}
              error={profileError}
              saveToDatabase={saveProfilesToDatabase}
              onSaveToDatabaseChange={setSaveProfilesToDatabase}
              showPushButton={false}
              progress={profileProgress}
              renderTable={() => (
                <DataTable
                  rows={profileRows}
                  emptyMessage="No Instagram profile data yet. Add usernames and run profile collection."
                  headers={[
                    "ID",
                    "Username",
                    "Full Name",
                    "Followers",
                    "Following",
                    "Posts",
                    "Category",
                    "Verified",
                    "Bio",
                    "External URL",
                    "Last Updated",
                    "Country",
                    "Industry",
                    "Project",
                  ]}
                  renderRow={(row) => [
                    row.id,
                    `@${row.username}`,
                    row.full_name,
                    formatNumber(row.followers),
                    formatNumber(row.following),
                    formatNumber(row.posts),
                    row.category,
                    row.is_verified ? "Yes" : "No",
                    row.bio,
                    row.external_url,
                    new Date(row.last_updated).toLocaleString(),
                    row.country,
                    row.industry,
                    row.project,
                  ]}
                />
              )}
            />
          ) : (
            <InstagramSection
              accent="#8b5cf6"
              soft="rgba(139,92,246,0.16)"
              title="Posts Data"
              description="Post-level output. Ready for the final posts API schema."
              usernameCount={usernameCount}
              rows={postRows}
              status={postStatus}
              canRun={canRunPosts}
              filename="instagram_posts_data_collection"
              sheetName="Instagram Posts"
              onRun={runPostCollection}
              onReset={resetPosts}
              onPush={() => setPostStatus("pushed")}
              error={postError}
              saveToDatabase={savePostsToDatabase}
              onSaveToDatabaseChange={setSavePostsToDatabase}
              showPushButton={false}
              progress={postProgress}
              extraControls={
                <InstagramPostControls
                  settings={postSettings}
                  onChange={setPostSettings}
                  disabled={postStatus === "running"}
                  dateError={postDateError}
                />
              }
              renderTable={() => (
                <DataTable
                  rows={postRows}
                  emptyMessage="No Instagram posts data yet. Add usernames and run posts collection."
                  headers={[
                    "ID",
                    "Username",
                    "Uploaded At",
                    "Caption",
                    "Views",
                    "Comments",
                    "Likes",
                    "Last Updated",
                    "Thumbnail URL",
                    "S3 Key",
                    "Image Status",
                  ]}
                  renderRow={(row) => [
                    row.id,
                    `@${row.username}`,
                    new Date(row.uploaded_at).toLocaleString(),
                    row.caption,
                    formatNumber(row.views),
                    formatNumber(row.comments),
                    formatNumber(row.likes),
                    new Date(row.last_updated).toLocaleString(),
                    row.thumbnail_url ?? "",
                    row.s3_key ?? "",
                    row.image_upload_status ?? "",
                  ]}
                />
              )}
            />
          )}
        </section>
      </div>

      {showProfileSaveConfirm ? (
        <SaveToDatabaseConfirmModal
          collectionName="Instagram profiles"
          usernameCount={usernameCount}
          project={inputs.project}
          onCancel={() => setShowProfileSaveConfirm(false)}
          onRunPreviewOnly={() => {
            setShowProfileSaveConfirm(false);
            setSaveProfilesToDatabase(false);
            void executeProfileCollection(false);
          }}
          onConfirm={() => {
            setShowProfileSaveConfirm(false);
            void executeProfileCollection(true);
          }}
        />
      ) : null}

      {showPostSaveConfirm ? (
        <SaveToDatabaseConfirmModal
          collectionName="Instagram posts"
          usernameCount={usernameCount}
          project={`${postSettings.startDate} to ${postSettings.endDate}`}
          onCancel={() => setShowPostSaveConfirm(false)}
          onRunPreviewOnly={() => {
            setShowPostSaveConfirm(false);
            setSavePostsToDatabase(false);
            void executePostCollection(false);
          }}
          onConfirm={() => {
            setShowPostSaveConfirm(false);
            void executePostCollection(true);
          }}
        />
      ) : null}
    </main>
  );
}

function TwitterCollectionPage() {
  const platform = PLATFORM_CONFIG.twitter;
  const [inputs, setInputs] = useState<TwitterInputs>({
    usernames: "",
    country: "",
    industry: "",
    project: "",
  });
  const [profileStatus, setProfileStatus] = useState<CollectionStatus>("idle");
  const [postStatus, setPostStatus] = useState<CollectionStatus>("idle");
  const [keywordStatus, setKeywordStatus] = useState<CollectionStatus>("idle");
  const [activeCollection, setActiveCollection] = useState<"profile" | "posts" | "keywords">("profile");
  const [accountDraft, setAccountDraft] = useState("");
  const [keywordDraft, setKeywordDraft] = useState("");
  const [postSettings, setPostSettings] = useState<TwitterPostSettings>({
    startDate: "2025-01-01",
    endDate: getTodayDateInputValue(),
  });
  const [keywordInputs, setKeywordInputs] = useState<TwitterKeywordInputs>({
    keywords: "",
    lang: "",
    locationQuery: "",
    countryFilterTerms: "",
  });
  const [keywordSettings, setKeywordSettings] = useState<TwitterKeywordSettings>({
    startDate: "2025-01-01",
    endDate: getTodayDateInputValue(),
    queryType: "Latest",
    filterByCountry: false,
    excludeRetweets: true,
    excludeReplies: false,
    windowDays: 31,
    maxPagesPerWindow: "",
  });
  const [profileRows, setProfileRows] = useState<TwitterProfileRow[]>([]);
  const [postRows, setPostRows] = useState<TwitterPostRow[]>([]);
  const [keywordRows, setKeywordRows] = useState<TwitterKeywordRow[]>([]);
  const [profileError, setProfileError] = useState<string | null>(null);
  const [postError, setPostError] = useState<string | null>(null);
  const [keywordError, setKeywordError] = useState<string | null>(null);
  const [saveProfilesToDatabase, setSaveProfilesToDatabase] = useState(true);
  const [savePostsToDatabase, setSavePostsToDatabase] = useState(true);
  const [saveKeywordsToDatabase, setSaveKeywordsToDatabase] = useState(true);
  const [showProfileSaveConfirm, setShowProfileSaveConfirm] = useState(false);
  const [showPostSaveConfirm, setShowPostSaveConfirm] = useState(false);
  const [showKeywordSaveConfirm, setShowKeywordSaveConfirm] = useState(false);
  const [profileProgress, setProfileProgress] = useState<TwitterProfileJobProgress | null>(null);
  const [postProgress, setPostProgress] = useState<TwitterPostJobProgress | null>(null);
  const [keywordProgress, setKeywordProgress] = useState<TwitterKeywordJobProgress | null>(null);

  const usernames = useMemo(() => parseUsernames(inputs.usernames), [inputs.usernames]);
  const keywords = useMemo(() => parseListValues(keywordInputs.keywords), [keywordInputs.keywords]);
  const usernameCount = usernames.length;
  const keywordCount = keywords.length;
  const postDateError =
    postSettings.startDate && postSettings.endDate && postSettings.endDate < postSettings.startDate
      ? "End date must be on or after start date."
      : null;
  const keywordDateError =
    keywordSettings.startDate && keywordSettings.endDate && keywordSettings.endDate < keywordSettings.startDate
      ? "End date must be on or after start date."
      : null;
  const canRunProfile = Boolean(usernameCount > 0 && inputs.country.trim() && inputs.industry.trim() && inputs.project.trim());
  const canRunPosts = Boolean(usernameCount > 0 && postSettings.startDate && postSettings.endDate && !postDateError);
  const canRunKeywords = Boolean(
    keywordCount > 0 &&
    keywordSettings.startDate &&
    keywordSettings.endDate &&
    !keywordDateError &&
    keywordSettings.windowDays > 0 &&
    inputs.country.trim() &&
    inputs.industry.trim() &&
    inputs.project.trim()
  );
  const canRun = canRunProfile || canRunPosts || canRunKeywords;

  const updateInput = (key: keyof TwitterInputs, value: string) => {
    setInputs((current) => ({ ...current, [key]: value }));
    if (profileStatus !== "running") setProfileStatus(profileRows.length ? "ready" : "idle");
    if (postStatus !== "running") setPostStatus(postRows.length ? "ready" : "idle");
  };

  const updateKeywordInput = (key: keyof TwitterKeywordInputs, value: string) => {
    setKeywordInputs((current) => ({ ...current, [key]: value }));
    if (keywordStatus !== "running") setKeywordStatus(keywordRows.length ? "ready" : "idle");
  };

  const updateUsernames = (nextUsernames: string[]) => {
    const unique = Array.from(new Set(parseUsernames(nextUsernames.join("\n"))));
    updateInput("usernames", unique.join("\n"));
  };

  const addDraftUsernames = (value = accountDraft) => {
    const next = parseUsernames(value);
    if (!next.length) return;
    updateUsernames([...usernames, ...next]);
    setAccountDraft("");
  };

  const updateKeywords = (nextKeywords: string[]) => {
    const unique = Array.from(new Set(parseListValues(nextKeywords.join("\n"))));
    updateKeywordInput("keywords", unique.join("\n"));
  };

  const addDraftKeywords = (value = keywordDraft) => {
    const next = parseListValues(value);
    if (!next.length) return;
    updateKeywords([...keywords, ...next]);
    setKeywordDraft("");
  };

  const executeProfileCollection = async (saveToDatabase = saveProfilesToDatabase) => {
    setProfileStatus("running");
    setProfileError(null);
    setProfileProgress(null);

    try {
      const result = await scrapeTwitterProfiles(
        {
          usernames,
          country: inputs.country,
          industry: inputs.industry,
          project: inputs.project,
          save_to_database: saveToDatabase,
        },
        (progress) => {
          setProfileProgress(progress);
          if (progress.profiles?.length) {
            setProfileRows(progress.profiles);
          }
        }
      );

      setProfileRows(result.profiles);
      setProfileStatus(result.saved_to_database ? "pushed" : "ready");
    } catch (error) {
      setProfileStatus("idle");
      setProfileError(error instanceof Error ? error.message : "Failed to collect Twitter profiles");
    }
  };

  const runProfileCollection = () => {
    if (!canRunProfile || profileStatus === "running") return;

    if (saveProfilesToDatabase) {
      setShowProfileSaveConfirm(true);
      return;
    }

    void executeProfileCollection(false);
  };

  const executePostCollection = async (saveToDatabase = savePostsToDatabase) => {
    if (postDateError) {
      setPostError(postDateError);
      return;
    }

    setPostStatus("running");
    setPostError(null);
    setPostProgress(null);

    try {
      const result = await scrapeTwitterPosts(
        {
          usernames,
          start_date: postSettings.startDate,
          end_date: postSettings.endDate,
          save_to_database: saveToDatabase,
        },
        (progress) => {
          setPostProgress(progress);
          if (progress.posts?.length) {
            setPostRows(progress.posts);
          }
        }
      );

      setPostRows(result.posts);
      setPostStatus(result.saved_to_database ? "pushed" : "ready");
    } catch (error) {
      setPostStatus("idle");
      setPostError(error instanceof Error ? error.message : "Failed to collect Twitter posts");
    }
  };

  const runPostCollection = () => {
    if (postDateError) {
      setPostError(postDateError);
      return;
    }

    if (!canRunPosts || postStatus === "running") return;

    if (savePostsToDatabase) {
      setShowPostSaveConfirm(true);
      return;
    }

    void executePostCollection(false);
  };

  const executeKeywordCollection = async (saveToDatabase = saveKeywordsToDatabase) => {
    if (keywordDateError) {
      setKeywordError(keywordDateError);
      return;
    }

    setKeywordStatus("running");
    setKeywordError(null);
    setKeywordProgress(null);

    try {
      const result = await scrapeTwitterKeywords(
        {
          keywords,
          start_date: keywordSettings.startDate,
          end_date: keywordSettings.endDate,
          query_type: keywordSettings.queryType,
          lang: keywordInputs.lang.trim() || null,
          location_query: keywordInputs.locationQuery.trim() || null,
          filter_by_country: keywordSettings.filterByCountry,
          country_filter_terms: parseListValues(keywordInputs.countryFilterTerms),
          exclude_retweets: keywordSettings.excludeRetweets,
          exclude_replies: keywordSettings.excludeReplies,
          window_days: keywordSettings.windowDays,
          max_pages_per_window: keywordSettings.maxPagesPerWindow.trim()
            ? Number(keywordSettings.maxPagesPerWindow)
            : null,
          project: inputs.project,
          country: inputs.country,
          industry: inputs.industry,
          save_to_database: saveToDatabase,
        },
        (progress) => {
          setKeywordProgress(progress);
          if (progress.posts?.length) {
            setKeywordRows(progress.posts);
          }
        }
      );

      setKeywordRows(result.posts);
      setKeywordStatus(result.saved_to_database ? "pushed" : "ready");
    } catch (error) {
      setKeywordStatus("idle");
      setKeywordError(error instanceof Error ? error.message : "Failed to collect Twitter keyword posts");
    }
  };

  const runKeywordCollection = () => {
    if (keywordDateError) {
      setKeywordError(keywordDateError);
      return;
    }

    if (!canRunKeywords || keywordStatus === "running") return;

    if (saveKeywordsToDatabase) {
      setShowKeywordSaveConfirm(true);
      return;
    }

    void executeKeywordCollection(false);
  };

  return (
    <main className="min-h-screen">
      <DashboardTopbar title="Internal Data Collection" />

      <div className="space-y-6 p-8">
        <section
          className="overflow-hidden rounded-2xl border p-6 shadow-xl backdrop-blur-xl"
          style={{
            borderColor: "rgba(15,23,42,0.14)",
            background:
              "linear-gradient(135deg, rgba(255,255,255,0.94), rgba(239,246,255,0.88) 44%, rgba(226,232,240,0.78))",
          }}
        >
          <div className="flex flex-wrap items-center justify-between gap-6">
            <div className="flex min-w-0 items-start gap-4">
              <div className="flex h-14 w-14 shrink-0 items-center justify-center rounded-2xl bg-slate-950 text-white shadow-xl shadow-slate-900/20">
                <Hash className="h-7 w-7" />
              </div>
              <div className="min-w-0">
                <div className="inline-flex rounded-full bg-white/72 px-3 py-1 text-xs font-black uppercase tracking-[0.18em] text-slate-700 shadow-sm">
                  Twitter Workspace
                </div>
                <h1 className="mt-3 text-3xl font-black tracking-tight" style={{ color: "var(--title-tx)" }}>
                  Collection Studio
                </h1>
                <p className="mt-2 max-w-3xl text-sm leading-6" style={{ color: "var(--muted-tx)" }}>
                  Add handles once, then collect Twitter profile data and post data as separate reviewable outputs.
                </p>
              </div>
            </div>

            <div className="grid min-w-[420px] gap-3 sm:grid-cols-3">
              {[
                ["Handles", usernameCount, "from input"],
                ["Profiles", profileRows.length, "ready rows"],
                ["Posts", postRows.length + keywordRows.length, "ready rows"],
              ].map(([label, value, caption]) => (
                <div
                  key={label}
                  className="rounded-2xl border bg-white/70 px-5 py-4 shadow-sm backdrop-blur-xl"
                  style={{ borderColor: "var(--card-bd)" }}
                >
                  <div className="text-[10px] font-black uppercase tracking-wider" style={{ color: "var(--muted-tx)" }}>
                    {label}
                  </div>
                  <div className="mt-1 text-3xl font-black tracking-tight" style={{ color: "var(--title-tx)" }}>
                    {value}
                  </div>
                  <div className="mt-1 text-[11px] font-bold text-slate-600">{caption}</div>
                </div>
              ))}
            </div>
          </div>
        </section>

        <section className="rounded-2xl border bg-white/78 p-5 shadow-lg backdrop-blur-xl dark:bg-slate-900/78" style={{ borderColor: "var(--card-bd)" }}>
          <div className="grid gap-5 xl:grid-cols-[minmax(420px,1.05fr)_0.95fr]">
            <div
              className="rounded-2xl border p-5 shadow-sm"
              style={{
                borderColor: "rgba(15,23,42,0.12)",
                background: "linear-gradient(135deg, rgba(255,255,255,0.92), rgba(241,245,249,0.76))",
              }}
            >
              <div className="flex flex-wrap items-start justify-between gap-4">
                <div>
                  <h2 className="text-2xl font-black tracking-tight" style={{ color: "var(--title-tx)" }}>
                    Batch Setup
                  </h2>
                  <p className="mt-1 text-sm leading-6" style={{ color: "var(--muted-tx)" }}>
                    Add Twitter handles once, then use the same batch for profile and posts collection.
                  </p>
                </div>
                <span
                  className="inline-flex h-9 items-center rounded-full px-4 text-xs font-black uppercase tracking-wider text-white shadow-lg"
                  style={{ background: canRun ? "#10b981" : "#94a3b8" }}
                >
                  {canRun ? "Ready" : "Needs input"}
                </span>
              </div>

              <div className="mt-5 rounded-2xl border bg-white/76 p-4 shadow-inner dark:bg-slate-950/25" style={{ borderColor: "var(--card-bd)" }}>
                <div className="flex items-center justify-between gap-4">
                  <label className="inline-flex items-center gap-2 text-xs font-black uppercase tracking-[0.18em] text-slate-700">
                    <Hash className="h-4 w-4" />
                    Twitter Handles
                  </label>
                  {usernameCount > 0 ? (
                    <button
                      type="button"
                      onClick={() => updateUsernames([])}
                      className="rounded-full bg-slate-100 px-3 py-1 text-xs font-black text-slate-500 transition hover:bg-slate-200"
                    >
                      Clear all
                    </button>
                  ) : (
                    <span className="rounded-full bg-slate-900/10 px-3 py-1 text-xs font-black text-slate-700">Empty</span>
                  )}
                </div>

                <div className="mt-4 flex gap-3">
                  <div className="flex min-w-0 flex-1 items-center rounded-xl border bg-white/82 px-4 shadow-sm focus-within:border-slate-500 focus-within:ring-4 focus-within:ring-slate-500/10 dark:bg-slate-900/40" style={{ borderColor: "var(--card-bd)" }}>
                    <span className="mr-1 text-lg font-black text-slate-700">@</span>
                    <input
                      value={accountDraft}
                      onChange={(event) => setAccountDraft(event.target.value)}
                      onKeyDown={(event) => {
                        if (event.key === "Enter" || event.key === ",") {
                          event.preventDefault();
                          addDraftUsernames();
                        }
                      }}
                      onPaste={(event) => {
                        const pasted = event.clipboardData.getData("text");
                        if (/[\n,]/.test(pasted)) {
                          event.preventDefault();
                          addDraftUsernames(`${accountDraft}\n${pasted}`);
                        }
                      }}
                      placeholder="type handle and press Enter"
                      className="h-12 min-w-0 flex-1 border-0 bg-transparent text-sm font-black outline-none placeholder:text-slate-400"
                      style={{ color: "var(--title-tx)" }}
                    />
                  </div>
                  <button
                    type="button"
                    onClick={() => addDraftUsernames()}
                    disabled={!parseUsernames(accountDraft).length}
                    className="inline-flex h-12 items-center gap-2 rounded-xl bg-slate-950 px-5 text-sm font-black text-white shadow-lg shadow-slate-900/20 transition hover:bg-slate-800 disabled:cursor-not-allowed disabled:opacity-45"
                  >
                    <Plus className="h-4 w-4" />
                    Add
                  </button>
                </div>

                <div className="mt-4 min-h-36 rounded-xl border border-dashed bg-white/54 p-3 dark:bg-slate-900/25" style={{ borderColor: "rgba(15,23,42,0.18)" }}>
                  {usernames.length ? (
                    <div className="flex flex-wrap gap-2">
                      {usernames.map((username) => (
                        <span
                          key={username}
                          className="inline-flex h-9 items-center gap-2 rounded-full border bg-white px-3 text-sm font-black shadow-sm dark:bg-slate-900/60"
                          style={{ borderColor: "var(--card-bd)", color: "var(--title-tx)" }}
                        >
                          @{username}
                          <button
                            type="button"
                            onClick={() => updateUsernames(usernames.filter((item) => item !== username))}
                            className="inline-flex h-5 w-5 items-center justify-center rounded-full bg-slate-100 text-slate-500 transition hover:bg-slate-200 hover:text-slate-900 dark:bg-slate-800"
                            aria-label={`Remove ${username}`}
                          >
                            <X className="h-3.5 w-3.5" />
                          </button>
                        </span>
                      ))}
                    </div>
                  ) : (
                    <div className="flex h-28 items-center justify-center rounded-lg text-center text-sm font-bold" style={{ color: "var(--muted-tx)" }}>
                      Add handles one by one, or paste a comma-separated list.
                    </div>
                  )}
                </div>
              </div>
            </div>

            <div className="rounded-2xl border bg-white/72 p-5 shadow-sm backdrop-blur-xl dark:bg-slate-950/30" style={{ borderColor: "var(--card-bd)" }}>
              <div className="flex items-center justify-between gap-4">
                <div>
                  <div className="text-xs font-black uppercase tracking-[0.22em]" style={{ color: "var(--muted-tx)" }}>
                    Batch Details
                  </div>
                  <h3 className="mt-1 text-xl font-black tracking-tight" style={{ color: "var(--title-tx)" }}>
                    Output Metadata
                  </h3>
                </div>
                <div className="flex h-11 w-11 items-center justify-center rounded-xl bg-slate-900 text-white shadow-lg shadow-slate-900/15 dark:bg-white dark:text-slate-950">
                  <FileSpreadsheet className="h-5 w-5" />
                </div>
              </div>

              <div className="mt-5 grid gap-3">
                {([
                  ["country", "Country", "SA"],
                  ["industry", "Industry", "Banking"],
                  ["project", "Project", "Internal Data Collection"],
                ] as const).map(([key, label, placeholder]) => (
                  <label
                    key={key}
                    className="block rounded-2xl border bg-white/68 px-4 py-3 focus-within:border-slate-500 focus-within:ring-4 focus-within:ring-slate-500/10 dark:bg-slate-900/35"
                    style={{ borderColor: "var(--card-bd)" }}
                  >
                    <span className="text-[10px] font-black uppercase tracking-wider" style={{ color: "var(--muted-tx)" }}>
                      {label}
                    </span>
                    <input
                      value={inputs[key]}
                      onChange={(event) => updateInput(key, event.target.value)}
                      placeholder={placeholder}
                      className="mt-1 h-8 w-full border-0 bg-transparent p-0 text-base font-black outline-none"
                      style={{ color: "var(--title-tx)" }}
                    />
                  </label>
                ))}
              </div>
            </div>
          </div>
        </section>

        <section className="rounded-2xl border bg-white/70 p-4 shadow-lg backdrop-blur-xl dark:bg-slate-900/70" style={{ borderColor: "var(--card-bd)" }}>
          <div className="mb-4 inline-flex rounded-2xl border bg-white/72 p-1 shadow-sm dark:bg-slate-950/35" style={{ borderColor: "var(--card-bd)" }}>
            {[
              { key: "profile" as const, label: "Profile Data", count: profileRows.length, accent: platform.accent },
              { key: "posts" as const, label: "Posts Data", count: postRows.length, accent: "#0ea5e9" },
              { key: "keywords" as const, label: "Keyword Data", count: keywordRows.length, accent: "#8b5cf6" },
            ].map((tab) => {
              const selected = activeCollection === tab.key;

              return (
                <button
                  key={tab.key}
                  type="button"
                  onClick={() => setActiveCollection(tab.key)}
                  className="inline-flex h-11 items-center gap-3 rounded-xl px-4 text-sm font-black transition"
                  style={{
                    background: selected ? tab.accent : "transparent",
                    color: selected ? "#ffffff" : "var(--muted-tx)",
                    boxShadow: selected
                      ? `0 12px 26px ${
                          tab.key === "profile"
                            ? platform.soft
                            : tab.key === "posts"
                              ? "rgba(14,165,233,0.18)"
                              : "rgba(139,92,246,0.2)"
                        }`
                      : "none",
                  }}
                >
                  {tab.label}
                  <span
                    className="inline-flex min-w-7 justify-center rounded-full px-2 py-0.5 text-xs"
                    style={{
                      background: selected ? "rgba(255,255,255,0.22)" : "rgba(100,116,139,0.12)",
                      color: selected ? "#ffffff" : "var(--body-tx)",
                    }}
                  >
                    {tab.count}
                  </span>
                </button>
              );
            })}
          </div>

          {activeCollection === "profile" ? (
            <InstagramSection
              accent={platform.accent}
              soft={platform.soft}
              title="Profile Data"
              description="Account metadata, verification status, created date, country, and industry."
              usernameCount={usernameCount}
              rows={profileRows}
              status={profileStatus}
              canRun={canRunProfile}
              filename="twitter_profile_data_collection"
              sheetName="Twitter Profiles"
              onRun={runProfileCollection}
              onReset={() => {
                setProfileRows([]);
                setProfileStatus("idle");
                setProfileError(null);
                setProfileProgress(null);
              }}
              onPush={() => setProfileStatus("pushed")}
              error={profileError}
              saveToDatabase={saveProfilesToDatabase}
              onSaveToDatabaseChange={setSaveProfilesToDatabase}
              showPushButton={false}
              progress={profileProgress}
              renderTable={() => (
                <DataTable
                  rows={profileRows}
                  emptyMessage="No Twitter profile data yet. Add handles and run profile collection."
                  headers={[
                    "ID",
                    "Username",
                    "Full Name",
                    "Followers",
                    "Following",
                    "Posts",
                    "Bio",
                    "Verified",
                    "Blue Verified",
                    "Verified Type",
                    "Created At",
                    "Last Updated",
                    "Country",
                    "Industry",
                    "Project",
                  ]}
                  renderRow={(row) => [
                    row.id,
                    `@${row.username}`,
                    row.full_name,
                    formatNumber(row.followers),
                    formatNumber(row.following),
                    formatNumber(row.posts),
                    row.bio ?? "",
                    row.is_verified ? "Yes" : "No",
                    row.is_blue_verified ? "Yes" : "No",
                    row.verified_type ?? "",
                    new Date(row.created_at).toLocaleString(),
                    new Date(row.last_updated).toLocaleString(),
                    row.country,
                    row.industry,
                    row.project ?? "",
                  ]}
                />
              )}
            />
          ) : activeCollection === "posts" ? (
            <InstagramSection
              accent="#0ea5e9"
              soft="rgba(14,165,233,0.16)"
              title="Posts Data"
              description="Tweet-level output with views, replies, retweets, and likes."
              usernameCount={usernameCount}
              rows={postRows}
              status={postStatus}
              canRun={canRunPosts}
              filename="twitter_posts_data_collection"
              sheetName="Twitter Posts"
              onRun={runPostCollection}
              onReset={() => {
                setPostRows([]);
                setPostStatus("idle");
                setPostError(null);
                setPostProgress(null);
              }}
              onPush={() => setPostStatus("pushed")}
              error={postError}
              saveToDatabase={savePostsToDatabase}
              onSaveToDatabaseChange={setSavePostsToDatabase}
              showPushButton={false}
              progress={postProgress}
              extraControls={
                <TwitterPostControls
                  settings={postSettings}
                  onChange={setPostSettings}
                  disabled={postStatus === "running"}
                  dateError={postDateError}
                />
              }
              renderTable={() => (
                <DataTable
                  rows={postRows}
                  emptyMessage="No Twitter posts data yet. Add handles and run posts collection."
                  headers={["ID", "Username", "Text", "Uploaded At", "Views", "Replies", "Retweet", "Likes", "Last Updated"]}
                  renderRow={(row) => [
                    row.id,
                    `@${row.username}`,
                    row.text,
                    row.uploaded_at,
                    formatNumber(row.views),
                    formatNumber(row.replies),
                    formatNumber(row.retweet),
                    formatNumber(row.likes),
                    row.last_updated,
                  ]}
                />
              )}
            />
          ) : (
            <InstagramSection
              accent="#8b5cf6"
              soft="rgba(139,92,246,0.16)"
              title="Keyword Data"
              description="Twitter keyword search output with tweet text, engagement, metadata, and filters."
              usernameCount={keywordCount}
              entityLabel="Keywords"
              rows={keywordRows}
              status={keywordStatus}
              canRun={canRunKeywords}
              filename="twitter_keyword_data_collection"
              sheetName="Twitter Keywords"
              onRun={runKeywordCollection}
              onReset={() => {
                setKeywordRows([]);
                setKeywordStatus("idle");
                setKeywordError(null);
                setKeywordProgress(null);
              }}
              onPush={() => setKeywordStatus("pushed")}
              error={keywordError}
              saveToDatabase={saveKeywordsToDatabase}
              onSaveToDatabaseChange={setSaveKeywordsToDatabase}
              showPushButton={false}
              progress={keywordProgress}
              extraControls={
                <TwitterKeywordControls
                  inputs={keywordInputs}
                  settings={keywordSettings}
                  keywords={keywords}
                  keywordDraft={keywordDraft}
                  disabled={keywordStatus === "running"}
                  dateError={keywordDateError}
                  onInputChange={updateKeywordInput}
                  onSettingsChange={setKeywordSettings}
                  onKeywordDraftChange={setKeywordDraft}
                  onAddKeywords={addDraftKeywords}
                  onRemoveKeyword={(keyword) => updateKeywords(keywords.filter((item) => item !== keyword))}
                  onClearKeywords={() => updateKeywords([])}
                />
              }
              renderTable={() => (
                <DataTable
                  rows={keywordRows}
                  emptyMessage="No Twitter keyword data yet. Add keywords and run keyword collection."
                  headers={[
                    "ID",
                    "Keyword",
                    "Username",
                    "Text",
                    "Uploaded At",
                    "Views",
                    "Replies",
                    "Retweet",
                    "Likes",
                    "Last Updated",
                    "Country",
                    "Industry",
                    "Project",
                  ]}
                  renderRow={(row) => [
                    row.id,
                    row.keyword ?? row.query ?? "",
                    row.username ? `@${row.username}` : "",
                    row.text,
                    row.uploaded_at,
                    formatNumber(row.views),
                    formatNumber(row.replies),
                    formatNumber(row.retweet),
                    formatNumber(row.likes),
                    row.last_updated,
                    row.country ?? inputs.country,
                    row.industry ?? inputs.industry,
                    row.project ?? inputs.project,
                  ]}
                />
              )}
            />
          )}
        </section>
      </div>

      {showProfileSaveConfirm ? (
        <SaveToDatabaseConfirmModal
          collectionName="Twitter profiles"
          usernameCount={usernameCount}
          project={inputs.project}
          onCancel={() => setShowProfileSaveConfirm(false)}
          onRunPreviewOnly={() => {
            setShowProfileSaveConfirm(false);
            setSaveProfilesToDatabase(false);
            void executeProfileCollection(false);
          }}
          onConfirm={() => {
            setShowProfileSaveConfirm(false);
            void executeProfileCollection(true);
          }}
        />
      ) : null}

      {showPostSaveConfirm ? (
        <SaveToDatabaseConfirmModal
          collectionName="Twitter posts"
          usernameCount={usernameCount}
          project={`${postSettings.startDate} to ${postSettings.endDate}`}
          onCancel={() => setShowPostSaveConfirm(false)}
          onRunPreviewOnly={() => {
            setShowPostSaveConfirm(false);
            setSavePostsToDatabase(false);
            void executePostCollection(false);
          }}
          onConfirm={() => {
            setShowPostSaveConfirm(false);
            void executePostCollection(true);
          }}
        />
      ) : null}

      {showKeywordSaveConfirm ? (
        <SaveToDatabaseConfirmModal
          collectionName="Twitter keyword posts"
          usernameCount={keywordCount}
          project={`${inputs.project || "selected project"} · ${keywordSettings.startDate} to ${keywordSettings.endDate}`}
          onCancel={() => setShowKeywordSaveConfirm(false)}
          onRunPreviewOnly={() => {
            setShowKeywordSaveConfirm(false);
            setSaveKeywordsToDatabase(false);
            void executeKeywordCollection(false);
          }}
          onConfirm={() => {
            setShowKeywordSaveConfirm(false);
            void executeKeywordCollection(true);
          }}
        />
      ) : null}
    </main>
  );
}

function TiktokCollectionPage() {
  const platform = PLATFORM_CONFIG.tiktok;
  const [inputs, setInputs] = useState<TiktokInputs>({
    profiles: "",
    country: "",
    industry: "",
    project: "",
  });
  const [profileSettings, setProfileSettings] = useState<TiktokProfileSettings>({
    maxItems: 1000,
    getFollowers: true,
    getFollowing: true,
  });
  const [postSettings, setPostSettings] = useState<TiktokPostSettings>({
    maxItems: 1000,
    startDate: "2025-01-01",
    endDate: getTodayDateInputValue(),
  });
  const [profileDraft, setProfileDraft] = useState("");
  const [activeCollection, setActiveCollection] = useState<"profile" | "posts">("profile");
  const [profileRows, setProfileRows] = useState<TiktokProfileRow[]>([]);
  const [postRows, setPostRows] = useState<TiktokPostRow[]>([]);
  const [profileStatus, setProfileStatus] = useState<CollectionStatus>("idle");
  const [postStatus, setPostStatus] = useState<CollectionStatus>("idle");
  const [profileError, setProfileError] = useState<string | null>(null);
  const [postError, setPostError] = useState<string | null>(null);
  const [profileProgress, setProfileProgress] = useState<TiktokProfileJobProgress | null>(null);
  const [postProgress, setPostProgress] = useState<TiktokPostJobProgress | null>(null);
  const [saveProfilesToDatabase, setSaveProfilesToDatabase] = useState(true);
  const [savePostsToDatabase, setSavePostsToDatabase] = useState(true);
  const [showProfileSaveConfirm, setShowProfileSaveConfirm] = useState(false);
  const [showPostSaveConfirm, setShowPostSaveConfirm] = useState(false);

  const profiles = useMemo(() => parseListValues(inputs.profiles), [inputs.profiles]);
  const profileCount = profiles.length;
  const postDateError =
    postSettings.startDate && postSettings.endDate && postSettings.endDate < postSettings.startDate
      ? "End date must be on or after start date."
      : null;
  const canRunProfiles = Boolean(
    profileCount > 0 &&
    profileSettings.maxItems > 0 &&
    inputs.country.trim() &&
    inputs.industry.trim() &&
    inputs.project.trim()
  );
  const canRunPosts = Boolean(
    profileCount > 0 &&
    postSettings.maxItems > 0 &&
    postSettings.startDate &&
    postSettings.endDate &&
    !postDateError &&
    inputs.country.trim() &&
    inputs.industry.trim() &&
    inputs.project.trim()
  );
  const canRun = canRunProfiles || canRunPosts;

  const updateInput = (key: keyof TiktokInputs, value: string) => {
    setInputs((current) => ({ ...current, [key]: value }));
    if (profileStatus !== "running") setProfileStatus(profileRows.length ? "ready" : "idle");
    if (postStatus !== "running") setPostStatus(postRows.length ? "ready" : "idle");
  };

  const updateProfiles = (nextProfiles: string[]) => {
    const unique = Array.from(new Set(parseListValues(nextProfiles.join("\n"))));
    updateInput("profiles", unique.join("\n"));
  };

  const addDraftProfiles = (value = profileDraft) => {
    const next = parseListValues(value);
    if (!next.length) return;
    updateProfiles([...profiles, ...next]);
    setProfileDraft("");
  };

  const executeProfileCollection = async (shouldSave = saveProfilesToDatabase) => {
    setProfileStatus("running");
    setProfileError(null);
    setProfileProgress(null);

    try {
      const result = await scrapeTiktokProfiles(
        {
          profiles,
          max_items: profileSettings.maxItems,
          get_followers: profileSettings.getFollowers,
          get_following: profileSettings.getFollowing,
          country: inputs.country,
          industry: inputs.industry,
          project: inputs.project,
          save_to_database: shouldSave,
        },
        (nextProgress) => {
          setProfileProgress(nextProgress);
          if (nextProgress.profiles?.length) {
            setProfileRows(nextProgress.profiles);
          }
        }
      );

      setProfileRows(result.profiles);
      setProfileStatus(result.saved_to_database ? "pushed" : "ready");
    } catch (collectionError) {
      setProfileStatus("idle");
      setProfileError(collectionError instanceof Error ? collectionError.message : "Failed to collect TikTok profiles");
    }
  };

  const runProfileCollection = () => {
    if (!canRunProfiles || profileStatus === "running") return;

    if (saveProfilesToDatabase) {
      setShowProfileSaveConfirm(true);
      return;
    }

    void executeProfileCollection(false);
  };

  const executePostCollection = async (shouldSave = savePostsToDatabase) => {
    if (postDateError) {
      setPostError(postDateError);
      return;
    }

    setPostStatus("running");
    setPostError(null);
    setPostProgress(null);

    try {
      const result = await scrapeTiktokPosts(
        {
          start_urls: profiles,
          start_date: postSettings.startDate,
          end_date: postSettings.endDate,
          max_items: postSettings.maxItems,
          country: inputs.country,
          industry: inputs.industry,
          project: inputs.project,
          save_to_database: shouldSave,
        },
        (nextProgress) => {
          setPostProgress(nextProgress);
          if (nextProgress.posts?.length) {
            setPostRows(nextProgress.posts);
          }
        }
      );

      setPostRows(result.posts);
      setPostStatus(result.saved_to_database ? "pushed" : "ready");
    } catch (collectionError) {
      setPostStatus("idle");
      setPostError(collectionError instanceof Error ? collectionError.message : "Failed to collect TikTok posts");
    }
  };

  const runPostCollection = () => {
    if (postDateError) {
      setPostError(postDateError);
      return;
    }

    if (!canRunPosts || postStatus === "running") return;

    if (savePostsToDatabase) {
      setShowPostSaveConfirm(true);
      return;
    }

    void executePostCollection(false);
  };

  return (
    <main className="min-h-screen">
      <DashboardTopbar title="Internal Data Collection" />

      <div className="space-y-6 p-8">
        <section
          className="overflow-hidden rounded-2xl border p-6 shadow-xl backdrop-blur-xl"
          style={{
            borderColor: "rgba(20,184,166,0.18)",
            background:
              "linear-gradient(135deg, rgba(255,255,255,0.94), rgba(240,253,250,0.88) 45%, rgba(236,253,245,0.78))",
          }}
        >
          <div className="flex flex-wrap items-center justify-between gap-6">
            <div className="flex min-w-0 items-start gap-4">
              <div className="flex h-14 w-14 shrink-0 items-center justify-center rounded-2xl text-white shadow-xl shadow-teal-500/20" style={{ background: platform.accent }}>
                <Play className="h-7 w-7" />
              </div>
              <div className="min-w-0">
                <div className="inline-flex rounded-full bg-white/72 px-3 py-1 text-xs font-black uppercase tracking-[0.18em] text-teal-700 shadow-sm">
                  TikTok Workspace
                </div>
                <h1 className="mt-3 text-3xl font-black tracking-tight" style={{ color: "var(--title-tx)" }}>
                  Collection Studio
                </h1>
                <p className="mt-2 max-w-3xl text-sm leading-6" style={{ color: "var(--muted-tx)" }}>
                  Add TikTok usernames or profile URLs, then collect profile metadata and post data as separate outputs.
                </p>
              </div>
            </div>

            <div className="grid min-w-[360px] gap-3 sm:grid-cols-2">
              {[
                ["Profiles", profileCount, "from input"],
                ["Rows", profileRows.length + postRows.length, "ready rows"],
              ].map(([label, value, caption]) => (
                <div key={label} className="rounded-2xl border bg-white/70 px-5 py-4 shadow-sm backdrop-blur-xl" style={{ borderColor: "var(--card-bd)" }}>
                  <div className="text-[10px] font-black uppercase tracking-wider" style={{ color: "var(--muted-tx)" }}>
                    {label}
                  </div>
                  <div className="mt-1 text-3xl font-black tracking-tight" style={{ color: "var(--title-tx)" }}>
                    {value}
                  </div>
                  <div className="mt-1 text-[11px] font-bold text-slate-600">{caption}</div>
                </div>
              ))}
            </div>
          </div>
        </section>

        <section className="rounded-2xl border bg-white/78 p-5 shadow-lg backdrop-blur-xl dark:bg-slate-900/78" style={{ borderColor: "var(--card-bd)" }}>
          <div className="grid gap-5 xl:grid-cols-[minmax(420px,1.05fr)_0.95fr]">
            <div className="rounded-2xl border bg-white/70 p-5 shadow-sm dark:bg-slate-950/30" style={{ borderColor: "var(--card-bd)" }}>
              <div className="flex flex-wrap items-start justify-between gap-4">
                <div>
                  <h2 className="text-2xl font-black tracking-tight" style={{ color: "var(--title-tx)" }}>
                    Batch Setup
                  </h2>
                  <p className="mt-1 text-sm leading-6" style={{ color: "var(--muted-tx)" }}>
                    Add usernames, @handles, or TikTok profile URLs.
                  </p>
                </div>
                <span className="inline-flex h-9 items-center rounded-full px-4 text-xs font-black uppercase tracking-wider text-white shadow-lg" style={{ background: canRun ? "#10b981" : "#94a3b8" }}>
                  {canRun ? "Ready" : "Needs input"}
                </span>
              </div>

              <div className="mt-5 flex gap-3">
                <input
                  value={profileDraft}
                  onChange={(event) => setProfileDraft(event.target.value)}
                  onKeyDown={(event) => {
                    if (event.key === "Enter" || event.key === ",") {
                      event.preventDefault();
                      addDraftProfiles();
                    }
                  }}
                  onPaste={(event) => {
                    const pasted = event.clipboardData.getData("text");
                    if (/[\n,]/.test(pasted)) {
                      event.preventDefault();
                      addDraftProfiles(`${profileDraft}\n${pasted}`);
                    }
                  }}
                  placeholder="aldar, @willsmith, https://www.tiktok.com/@rabbitbrandmy"
                  className="h-12 min-w-0 flex-1 rounded-xl border bg-white/82 px-4 text-sm font-black outline-none dark:bg-slate-900/40"
                  style={{ borderColor: "var(--card-bd)", color: "var(--title-tx)" }}
                />
                <button
                  type="button"
                  onClick={() => addDraftProfiles()}
                  disabled={!parseListValues(profileDraft).length}
                  className="inline-flex h-12 items-center gap-2 rounded-xl px-5 text-sm font-black text-white shadow-lg transition disabled:cursor-not-allowed disabled:opacity-45"
                  style={{ background: platform.accent, boxShadow: `0 14px 28px ${platform.soft}` }}
                >
                  <Plus className="h-4 w-4" />
                  Add
                </button>
              </div>

              <div className="mt-4 min-h-32 rounded-xl border border-dashed bg-white/54 p-3 dark:bg-slate-900/25" style={{ borderColor: "rgba(20,184,166,0.24)" }}>
                {profiles.length ? (
                  <div className="flex flex-wrap gap-2">
                    {profiles.map((profile) => (
                      <span key={profile} className="inline-flex h-9 max-w-full items-center gap-2 rounded-full border bg-white px-3 text-sm font-black shadow-sm dark:bg-slate-900/60" style={{ borderColor: "var(--card-bd)", color: "var(--title-tx)" }}>
                        <span className="max-w-[260px] truncate">{profile}</span>
                        <button
                          type="button"
                          onClick={() => updateProfiles(profiles.filter((item) => item !== profile))}
                          className="inline-flex h-5 w-5 items-center justify-center rounded-full bg-teal-50 text-teal-600 transition hover:bg-teal-100"
                          aria-label={`Remove ${profile}`}
                        >
                          <X className="h-3.5 w-3.5" />
                        </button>
                      </span>
                    ))}
                  </div>
                ) : (
                  <div className="flex h-24 items-center justify-center text-center text-sm font-bold" style={{ color: "var(--muted-tx)" }}>
                    Add profiles one by one, or paste a comma-separated list.
                  </div>
                )}
              </div>
            </div>

            <div className="rounded-2xl border bg-white/72 p-5 shadow-sm backdrop-blur-xl dark:bg-slate-950/30" style={{ borderColor: "var(--card-bd)" }}>
              <div className="flex items-center justify-between gap-4">
                <div>
                  <div className="text-xs font-black uppercase tracking-[0.22em]" style={{ color: "var(--muted-tx)" }}>
                    Batch Details
                  </div>
                  <h3 className="mt-1 text-xl font-black tracking-tight" style={{ color: "var(--title-tx)" }}>
                    Output Metadata
                  </h3>
                </div>
                <div className="flex h-11 w-11 items-center justify-center rounded-xl bg-slate-900 text-white shadow-lg shadow-slate-900/15 dark:bg-white dark:text-slate-950">
                  <FileSpreadsheet className="h-5 w-5" />
                </div>
              </div>

              <div className="mt-5 grid gap-3">
                {([
                  ["country", "Country", "UAE"],
                  ["industry", "Industry", "Real Estate"],
                  ["project", "Project", "realestate_dbh"],
                ] as const).map(([key, label, placeholder]) => (
                  <label key={key} className="block rounded-2xl border bg-white/68 px-4 py-3 focus-within:border-teal-500 focus-within:ring-4 focus-within:ring-teal-500/10 dark:bg-slate-900/35" style={{ borderColor: "var(--card-bd)" }}>
                    <span className="text-[10px] font-black uppercase tracking-wider" style={{ color: "var(--muted-tx)" }}>
                      {label}
                    </span>
                    <input
                      value={inputs[key]}
                      onChange={(event) => updateInput(key, event.target.value)}
                      placeholder={placeholder}
                      className="mt-1 h-8 w-full border-0 bg-transparent p-0 text-base font-black outline-none"
                      style={{ color: "var(--title-tx)" }}
                    />
                  </label>
                ))}
              </div>

              <TiktokProfileControls
                settings={activeCollection === "profile" ? profileSettings : postSettings}
                onChange={(nextSettings) => {
                  if (activeCollection === "profile") {
                    setProfileSettings(nextSettings as TiktokProfileSettings);
                  } else {
                    setPostSettings(nextSettings as TiktokPostSettings);
                  }
                }}
                disabled={profileStatus === "running" || postStatus === "running"}
                showFollowerOptions={activeCollection === "profile"}
              />
            </div>
          </div>
        </section>

        <section className="rounded-2xl border bg-white/70 p-4 shadow-lg backdrop-blur-xl dark:bg-slate-900/70" style={{ borderColor: "var(--card-bd)" }}>
          <div className="mb-4 inline-flex rounded-2xl border bg-white/72 p-1 shadow-sm dark:bg-slate-950/35" style={{ borderColor: "var(--card-bd)" }}>
            {[
              { key: "profile" as const, label: "Profile Data", count: profileRows.length, accent: platform.accent },
              { key: "posts" as const, label: "Posts Data", count: postRows.length, accent: "#0ea5e9" },
            ].map((tab) => {
              const selected = activeCollection === tab.key;

              return (
                <button
                  key={tab.key}
                  type="button"
                  onClick={() => setActiveCollection(tab.key)}
                  className="inline-flex h-11 items-center gap-3 rounded-xl px-4 text-sm font-black transition"
                  style={{
                    background: selected ? tab.accent : "transparent",
                    color: selected ? "#ffffff" : "var(--muted-tx)",
                    boxShadow: selected ? `0 12px 26px ${tab.key === "profile" ? platform.soft : "rgba(14,165,233,0.18)"}` : "none",
                  }}
                >
                  {tab.label}
                  <span
                    className="inline-flex min-w-7 justify-center rounded-full px-2 py-0.5 text-xs"
                    style={{
                      background: selected ? "rgba(255,255,255,0.22)" : "rgba(100,116,139,0.12)",
                      color: selected ? "#ffffff" : "var(--body-tx)",
                    }}
                  >
                    {tab.count}
                  </span>
                </button>
              );
            })}
          </div>

          {activeCollection === "profile" ? (
            <InstagramSection
          accent={platform.accent}
          soft={platform.soft}
          title="Profile Data"
          description="TikTok account metadata, audience counts, verification, profile category, and avatar."
          usernameCount={profileCount}
          entityLabel="Profiles"
          rows={profileRows}
          status={profileStatus}
          canRun={canRunProfiles}
          filename="tiktok_profile_data_collection"
          sheetName="TikTok Profiles"
          onRun={runProfileCollection}
          onReset={() => {
            setProfileRows([]);
            setProfileStatus("idle");
            setProfileError(null);
            setProfileProgress(null);
          }}
          onPush={() => setProfileStatus("pushed")}
          error={profileError}
          saveToDatabase={saveProfilesToDatabase}
          onSaveToDatabaseChange={setSaveProfilesToDatabase}
          showPushButton={false}
          progress={profileProgress}
          renderTable={() => (
            <DataTable
              rows={profileRows}
              emptyMessage="No TikTok profile data yet. Add profiles and run collection."
              headers={[
                "ID",
                "Username",
                "Nickname",
                "URL",
                "Bio",
                "Bio URL",
                "Followers",
                "Following",
                "Likes",
                "Videos",
                "Verified",
                "Category",
                "Country",
                "Industry",
                "Project",
                "Last Updated",
              ]}
              renderRow={(row) => [
                row.id,
                `@${row.username}`,
                row.nickname,
                row.url,
                row.bio ?? "",
                row.bio_url ?? "",
                formatNumber(row.followers),
                formatNumber(row.following),
                formatNumber(row.likes),
                formatNumber(row.videos),
                row.is_verified ? "Yes" : "No",
                row.profile_category ?? "",
                row.country,
                row.industry,
                row.project,
                new Date(row.last_updated).toLocaleString(),
              ]}
            />
          )}
        />
          ) : (
            <InstagramSection
              accent="#0ea5e9"
              soft="rgba(14,165,233,0.16)"
              title="Posts Data"
              description="TikTok post collection by profile URLs with scraped post progress."
              usernameCount={profileCount}
              entityLabel="URLs"
              rows={postRows}
              status={postStatus}
              canRun={canRunPosts}
              filename="tiktok_posts_data_collection"
              sheetName="TikTok Posts"
              onRun={runPostCollection}
              onReset={() => {
                setPostRows([]);
                setPostStatus("idle");
                setPostError(null);
                setPostProgress(null);
              }}
              onPush={() => setPostStatus("pushed")}
              error={postError}
              saveToDatabase={savePostsToDatabase}
              onSaveToDatabaseChange={setSavePostsToDatabase}
              showPushButton={false}
              progress={postProgress}
              extraControls={
                <TwitterPostControls
                  settings={postSettings}
                  onChange={(nextSettings) => {
                    setPostSettings((current) => ({ ...current, ...nextSettings }));
                  }}
                  disabled={postStatus === "running"}
                  dateError={postDateError}
                />
              }
              renderTable={() => (
                <DataTable
                  rows={postRows}
                  emptyMessage="No TikTok posts data yet. Add profile URLs and run posts collection."
                  headers={[
                    "ID",
                    "Username",
                    "URL",
                    "Caption",
                    "Uploaded At",
                    "Views",
                    "Comments",
                    "Likes",
                    "Shares",
                    "Country",
                    "Industry",
                    "Project",
                    "Last Updated",
                  ]}
                  renderRow={(row) => [
                    row.id ?? "",
                    row.username ? `@${row.username}` : "",
                    row.url ?? "",
                    row.caption ?? row.text ?? "",
                    row.uploaded_at ?? "",
                    formatNumber(row.views ?? 0),
                    formatNumber(row.comments ?? 0),
                    formatNumber(row.likes ?? 0),
                    formatNumber(row.shares ?? 0),
                    row.country ?? inputs.country,
                    row.industry ?? inputs.industry,
                    row.project ?? inputs.project,
                    row.last_updated ?? "",
                  ]}
                />
              )}
            />
          )}
        </section>
      </div>

      {showProfileSaveConfirm ? (
        <SaveToDatabaseConfirmModal
          collectionName="TikTok profiles"
          usernameCount={profileCount}
          project={inputs.project}
          onCancel={() => setShowProfileSaveConfirm(false)}
          onRunPreviewOnly={() => {
            setShowProfileSaveConfirm(false);
            setSaveProfilesToDatabase(false);
            void executeProfileCollection(false);
          }}
          onConfirm={() => {
            setShowProfileSaveConfirm(false);
            void executeProfileCollection(true);
          }}
        />
      ) : null}

      {showPostSaveConfirm ? (
        <SaveToDatabaseConfirmModal
          collectionName="TikTok posts"
          usernameCount={profileCount}
          project={inputs.project}
          onCancel={() => setShowPostSaveConfirm(false)}
          onRunPreviewOnly={() => {
            setShowPostSaveConfirm(false);
            setSavePostsToDatabase(false);
            void executePostCollection(false);
          }}
          onConfirm={() => {
            setShowPostSaveConfirm(false);
            void executePostCollection(true);
          }}
        />
      ) : null}
    </main>
  );
}

function SaveToDatabaseConfirmModal({
  collectionName,
  usernameCount,
  project,
  onCancel,
  onRunPreviewOnly,
  onConfirm,
}: {
  collectionName: string;
  usernameCount: number;
  project: string;
  onCancel: () => void;
  onRunPreviewOnly: () => void;
  onConfirm: () => void;
}) {
  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-slate-950/45 p-4 backdrop-blur-sm">
      <div
        className="w-full max-w-lg overflow-hidden rounded-2xl border bg-white shadow-2xl dark:bg-slate-950"
        style={{ borderColor: "var(--card-bd)" }}
        role="dialog"
        aria-modal="true"
        aria-labelledby="save-to-db-title"
      >
        <div
          className="p-5"
          style={{
            background:
              "linear-gradient(135deg, rgba(255,255,255,0.96), rgba(236,253,245,0.86), rgba(253,242,248,0.78))",
          }}
        >
          <div className="flex items-start justify-between gap-4">
            <div className="flex items-start gap-4">
              <div className="flex h-12 w-12 shrink-0 items-center justify-center rounded-2xl bg-emerald-500 text-white shadow-lg shadow-emerald-500/20">
                <DatabaseZap className="h-6 w-6" />
              </div>
              <div>
                <h2 id="save-to-db-title" className="text-xl font-black tracking-tight" style={{ color: "var(--title-tx)" }}>
                  Save to database is on
                </h2>
                <p className="mt-2 text-sm leading-6" style={{ color: "var(--muted-tx)" }}>
                  Running this collection will scrape {collectionName} and push the approved result into the database.
                </p>
              </div>
            </div>
            <button
              type="button"
              onClick={onCancel}
              className="inline-flex h-9 w-9 shrink-0 items-center justify-center rounded-full bg-white/70 text-slate-500 shadow-sm transition hover:bg-white hover:text-slate-900"
              aria-label="Close save to database confirmation"
            >
              <X className="h-4 w-4" />
            </button>
          </div>

          <div className="mt-5 grid gap-3 sm:grid-cols-2">
            <div className="rounded-2xl border bg-white/72 px-4 py-3" style={{ borderColor: "var(--card-bd)" }}>
              <div className="text-[10px] font-black uppercase tracking-wider" style={{ color: "var(--muted-tx)" }}>
                Accounts
              </div>
              <div className="mt-1 text-2xl font-black" style={{ color: "var(--title-tx)" }}>
                {usernameCount}
              </div>
            </div>
            <div className="rounded-2xl border bg-white/72 px-4 py-3" style={{ borderColor: "var(--card-bd)" }}>
              <div className="text-[10px] font-black uppercase tracking-wider" style={{ color: "var(--muted-tx)" }}>
                Project
              </div>
              <div className="mt-1 truncate text-lg font-black" style={{ color: "var(--title-tx)" }}>
                {project}
              </div>
            </div>
          </div>

          <div className="mt-4 rounded-2xl border border-amber-200 bg-amber-50 px-4 py-3 text-sm font-bold leading-6 text-amber-800">
            If you only want to review the data or export Excel, choose preview only. Nothing will be saved to the database.
          </div>
        </div>

        <div className="flex flex-wrap items-center justify-end gap-3 border-t bg-white/88 p-4 dark:bg-slate-950/88" style={{ borderColor: "var(--card-bd)" }}>
          <button
            type="button"
            onClick={onCancel}
            className="inline-flex h-11 items-center rounded-full border px-5 text-sm font-black transition hover:bg-slate-50 dark:hover:bg-slate-900"
            style={{ borderColor: "var(--card-bd)", color: "var(--body-tx)" }}
          >
            Cancel
          </button>
          <button
            type="button"
            onClick={onRunPreviewOnly}
            className="inline-flex h-11 items-center rounded-full border bg-white px-5 text-sm font-black text-slate-700 shadow-sm transition hover:bg-slate-50"
            style={{ borderColor: "var(--card-bd)" }}
          >
            Run Preview Only
          </button>
          <button
            type="button"
            onClick={onConfirm}
            className="inline-flex h-11 items-center gap-2 rounded-full bg-emerald-500 px-5 text-sm font-black text-white shadow-lg shadow-emerald-500/20 transition hover:bg-emerald-600"
          >
            <DatabaseZap className="h-4 w-4" />
            Run & Save to DB
          </button>
        </div>
      </div>
    </div>
  );
}

function InstagramPostControls({
  settings,
  onChange,
  disabled,
  dateError,
}: {
  settings: InstagramPostSettings;
  onChange: (settings: InstagramPostSettings) => void;
  disabled: boolean;
  dateError?: string | null;
}) {
  const update = <TKey extends keyof InstagramPostSettings>(key: TKey, value: InstagramPostSettings[TKey]) => {
    onChange({ ...settings, [key]: value });
  };

  return (
    <div className="mt-4 rounded-2xl border bg-white/60 p-3 dark:bg-slate-950/30" style={{ borderColor: dateError ? "#fecaca" : "var(--card-bd)" }}>
      <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
        <label className="block">
          <span className="text-[10px] font-black uppercase tracking-wider" style={{ color: "var(--muted-tx)" }}>
            Start Date
          </span>
          <input
            type="date"
            value={settings.startDate}
            max={settings.endDate || undefined}
            disabled={disabled}
            onChange={(event) => update("startDate", event.target.value)}
            className="mt-1 h-10 w-full rounded-xl border bg-white/76 px-3 text-sm font-black outline-none disabled:opacity-60 dark:bg-slate-900/40"
            style={{ borderColor: dateError ? "#fca5a5" : "var(--card-bd)", color: "var(--title-tx)" }}
          />
        </label>
        <label className="block">
          <span className="text-[10px] font-black uppercase tracking-wider" style={{ color: "var(--muted-tx)" }}>
            End Date
          </span>
          <input
            type="date"
            value={settings.endDate}
            min={settings.startDate || undefined}
            disabled={disabled}
            onChange={(event) => update("endDate", event.target.value)}
            className="mt-1 h-10 w-full rounded-xl border bg-white/76 px-3 text-sm font-black outline-none disabled:opacity-60 dark:bg-slate-900/40"
            style={{ borderColor: dateError ? "#fca5a5" : "var(--card-bd)", color: "var(--title-tx)" }}
          />
        </label>
        <button
          type="button"
          disabled={disabled}
          onClick={() => update("uploadImagesToS3", !settings.uploadImagesToS3)}
          className="mt-5 inline-flex h-10 items-center justify-center gap-2 rounded-xl border px-3 text-sm font-black transition disabled:opacity-60"
          style={{
            borderColor: settings.uploadImagesToS3 ? "#8b5cf6" : "var(--card-bd)",
            background: settings.uploadImagesToS3 ? "rgba(139,92,246,0.13)" : "rgba(255,255,255,0.5)",
            color: settings.uploadImagesToS3 ? "#6d28d9" : "var(--body-tx)",
          }}
        >
          <span
            className="relative inline-flex h-5 w-9 rounded-full transition"
            style={{ background: settings.uploadImagesToS3 ? "#8b5cf6" : "#cbd5e1" }}
          >
            <span
              className="absolute top-0.5 h-4 w-4 rounded-full bg-white shadow-sm transition"
              style={{ left: settings.uploadImagesToS3 ? "18px" : "2px" }}
            />
          </span>
          Upload Images
        </button>
      </div>
      {dateError ? (
        <div className="mt-3 rounded-xl bg-red-50 px-3 py-2 text-xs font-black text-red-700">
          {dateError}
        </div>
      ) : null}
    </div>
  );
}

function TwitterPostControls({
  settings,
  onChange,
  disabled,
  dateError,
}: {
  settings: TwitterPostSettings;
  onChange: (settings: TwitterPostSettings) => void;
  disabled: boolean;
  dateError?: string | null;
}) {
  const update = <TKey extends keyof TwitterPostSettings>(key: TKey, value: TwitterPostSettings[TKey]) => {
    onChange({ ...settings, [key]: value });
  };

  return (
    <div className="mt-4 rounded-2xl border bg-white/60 p-3 dark:bg-slate-950/30" style={{ borderColor: dateError ? "#fecaca" : "var(--card-bd)" }}>
      <div className="grid gap-3 sm:grid-cols-2">
        <label className="block">
          <span className="text-[10px] font-black uppercase tracking-wider" style={{ color: "var(--muted-tx)" }}>
            Start Date
          </span>
          <input
            type="date"
            value={settings.startDate}
            max={settings.endDate || undefined}
            disabled={disabled}
            onChange={(event) => update("startDate", event.target.value)}
            className="mt-1 h-10 w-full rounded-xl border bg-white/76 px-3 text-sm font-black outline-none disabled:opacity-60 dark:bg-slate-900/40"
            style={{ borderColor: dateError ? "#fca5a5" : "var(--card-bd)", color: "var(--title-tx)" }}
          />
        </label>
        <label className="block">
          <span className="text-[10px] font-black uppercase tracking-wider" style={{ color: "var(--muted-tx)" }}>
            End Date
          </span>
          <input
            type="date"
            value={settings.endDate}
            min={settings.startDate || undefined}
            disabled={disabled}
            onChange={(event) => update("endDate", event.target.value)}
            className="mt-1 h-10 w-full rounded-xl border bg-white/76 px-3 text-sm font-black outline-none disabled:opacity-60 dark:bg-slate-900/40"
            style={{ borderColor: dateError ? "#fca5a5" : "var(--card-bd)", color: "var(--title-tx)" }}
          />
        </label>
      </div>
      {dateError ? (
        <div className="mt-3 rounded-xl bg-red-50 px-3 py-2 text-xs font-black text-red-700">
          {dateError}
        </div>
      ) : null}
    </div>
  );
}

function LinkedinPostControls({
  settings,
  onChange,
  disabled,
  dateError,
}: {
  settings: LinkedinPostSettings;
  onChange: (settings: LinkedinPostSettings) => void;
  disabled: boolean;
  dateError?: string | null;
}) {
  const update = <TKey extends keyof LinkedinPostSettings>(key: TKey, value: LinkedinPostSettings[TKey]) => {
    onChange({ ...settings, [key]: value });
  };

  return (
    <div className="mt-4 rounded-2xl border bg-white/60 p-3 dark:bg-slate-950/30" style={{ borderColor: dateError ? "#fecaca" : "var(--card-bd)" }}>
      <div className="grid gap-3 sm:grid-cols-3">
        <label className="block">
          <span className="text-[10px] font-black uppercase tracking-wider" style={{ color: "var(--muted-tx)" }}>Max Posts</span>
          <input type="number" min={1} value={settings.maxPosts} disabled={disabled} onChange={(event) => update("maxPosts", Number(event.target.value))} className="mt-1 h-10 w-full rounded-xl border bg-white/76 px-3 text-sm font-black outline-none disabled:opacity-60 dark:bg-slate-900/40" style={{ borderColor: "var(--card-bd)", color: "var(--title-tx)" }} />
        </label>
        <label className="block">
          <span className="text-[10px] font-black uppercase tracking-wider" style={{ color: "var(--muted-tx)" }}>Start Date</span>
          <input type="date" value={settings.startDate} max={settings.endDate || undefined} disabled={disabled} onChange={(event) => update("startDate", event.target.value)} className="mt-1 h-10 w-full rounded-xl border bg-white/76 px-3 text-sm font-black outline-none disabled:opacity-60 dark:bg-slate-900/40" style={{ borderColor: dateError ? "#fca5a5" : "var(--card-bd)", color: "var(--title-tx)" }} />
        </label>
        <label className="block">
          <span className="text-[10px] font-black uppercase tracking-wider" style={{ color: "var(--muted-tx)" }}>End Date</span>
          <input type="date" value={settings.endDate} min={settings.startDate || undefined} disabled={disabled} onChange={(event) => update("endDate", event.target.value)} className="mt-1 h-10 w-full rounded-xl border bg-white/76 px-3 text-sm font-black outline-none disabled:opacity-60 dark:bg-slate-900/40" style={{ borderColor: dateError ? "#fca5a5" : "var(--card-bd)", color: "var(--title-tx)" }} />
        </label>
      </div>
      {dateError ? <div className="mt-3 rounded-xl bg-red-50 px-3 py-2 text-xs font-black text-red-700">{dateError}</div> : null}
    </div>
  );
}

function TwitterKeywordControls({
  inputs,
  settings,
  keywords,
  keywordDraft,
  disabled,
  dateError,
  onInputChange,
  onSettingsChange,
  onKeywordDraftChange,
  onAddKeywords,
  onRemoveKeyword,
  onClearKeywords,
}: {
  inputs: TwitterKeywordInputs;
  settings: TwitterKeywordSettings;
  keywords: string[];
  keywordDraft: string;
  disabled: boolean;
  dateError?: string | null;
  onInputChange: (key: keyof TwitterKeywordInputs, value: string) => void;
  onSettingsChange: (settings: TwitterKeywordSettings) => void;
  onKeywordDraftChange: (value: string) => void;
  onAddKeywords: (value?: string) => void;
  onRemoveKeyword: (keyword: string) => void;
  onClearKeywords: () => void;
}) {
  const updateSetting = <TKey extends keyof TwitterKeywordSettings>(key: TKey, value: TwitterKeywordSettings[TKey]) => {
    onSettingsChange({ ...settings, [key]: value });
  };

  return (
    <div className="mt-4 grid gap-4 xl:grid-cols-[minmax(340px,0.9fr)_1.1fr]">
      <div className="rounded-2xl border bg-white/62 p-4 shadow-sm dark:bg-slate-950/30" style={{ borderColor: "var(--card-bd)" }}>
        <div className="flex items-center justify-between gap-3">
          <label className="inline-flex items-center gap-2 text-xs font-black uppercase tracking-[0.18em]" style={{ color: "var(--muted-tx)" }}>
            <Hash className="h-4 w-4 text-violet-600" />
            Keywords
          </label>
          {keywords.length ? (
            <button
              type="button"
              onClick={onClearKeywords}
              disabled={disabled}
              className="rounded-full bg-violet-50 px-3 py-1 text-xs font-black text-violet-700 transition hover:bg-violet-100 disabled:opacity-50"
            >
              Clear all
            </button>
          ) : (
            <span className="rounded-full bg-violet-50 px-3 py-1 text-xs font-black text-violet-700">Empty</span>
          )}
        </div>

        <div className="mt-3 flex gap-2">
          <input
            value={keywordDraft}
            onChange={(event) => onKeywordDraftChange(event.target.value)}
            onKeyDown={(event) => {
              if (event.key === "Enter" || event.key === ",") {
                event.preventDefault();
                onAddKeywords();
              }
            }}
            onPaste={(event) => {
              const pasted = event.clipboardData.getData("text");
              if (/[\n,]/.test(pasted)) {
                event.preventDefault();
                onAddKeywords(`${keywordDraft}\n${pasted}`);
              }
            }}
            disabled={disabled}
            placeholder="oral hygiene, #DentalCare"
            className="h-11 min-w-0 flex-1 rounded-xl border bg-white/78 px-3 text-sm font-black outline-none disabled:opacity-60 dark:bg-slate-900/40"
            style={{ borderColor: "var(--card-bd)", color: "var(--title-tx)" }}
          />
          <button
            type="button"
            onClick={() => onAddKeywords()}
            disabled={disabled || !parseListValues(keywordDraft).length}
            className="inline-flex h-11 items-center gap-2 rounded-xl bg-violet-600 px-4 text-sm font-black text-white shadow-lg shadow-violet-500/20 transition hover:bg-violet-700 disabled:cursor-not-allowed disabled:opacity-45"
          >
            <Plus className="h-4 w-4" />
            Add
          </button>
        </div>

        <div className="mt-3 min-h-24 rounded-xl border border-dashed bg-white/44 p-3 dark:bg-slate-900/25" style={{ borderColor: "rgba(139,92,246,0.22)" }}>
          {keywords.length ? (
            <div className="flex flex-wrap gap-2">
              {keywords.map((keyword) => (
                <span
                  key={keyword}
                  className="inline-flex h-8 items-center gap-2 rounded-full border bg-white px-3 text-xs font-black shadow-sm dark:bg-slate-900/60"
                  style={{ borderColor: "rgba(139,92,246,0.22)", color: "var(--title-tx)" }}
                >
                  {keyword}
                  <button
                    type="button"
                    onClick={() => onRemoveKeyword(keyword)}
                    disabled={disabled}
                    className="inline-flex h-5 w-5 items-center justify-center rounded-full bg-violet-50 text-violet-600 transition hover:bg-violet-100 disabled:opacity-50"
                    aria-label={`Remove ${keyword}`}
                  >
                    <X className="h-3.5 w-3.5" />
                  </button>
                </span>
              ))}
            </div>
          ) : (
            <div className="flex h-16 items-center justify-center text-center text-sm font-bold" style={{ color: "var(--muted-tx)" }}>
              Add one keyword per chip, or paste a comma-separated keyword list.
            </div>
          )}
        </div>
      </div>

      <div className="rounded-2xl border bg-white/62 p-4 shadow-sm dark:bg-slate-950/30" style={{ borderColor: dateError ? "#fecaca" : "var(--card-bd)" }}>
        <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-3">
          {([
            ["lang", "Language", "optional"],
            ["locationQuery", "Location Query", "optional"],
            ["countryFilterTerms", "Country Filter Terms", "Dubai, دبي"],
          ] as const).map(([key, label, placeholder]) => (
            <label key={key} className="block">
              <span className="text-[10px] font-black uppercase tracking-wider" style={{ color: "var(--muted-tx)" }}>
                {label}
              </span>
              <input
                value={inputs[key]}
                onChange={(event) => onInputChange(key, event.target.value)}
                disabled={disabled}
                placeholder={placeholder}
                className="mt-1 h-10 w-full rounded-xl border bg-white/76 px-3 text-sm font-black outline-none disabled:opacity-60 dark:bg-slate-900/40"
                style={{ borderColor: "var(--card-bd)", color: "var(--title-tx)" }}
              />
            </label>
          ))}

          <label className="block">
            <span className="text-[10px] font-black uppercase tracking-wider" style={{ color: "var(--muted-tx)" }}>
              Query Type
            </span>
            <select
              value={settings.queryType}
              onChange={(event) => updateSetting("queryType", event.target.value as TwitterKeywordSettings["queryType"])}
              disabled={disabled}
              className="mt-1 h-10 w-full rounded-xl border bg-white/76 px-3 text-sm font-black outline-none disabled:opacity-60 dark:bg-slate-900/40"
              style={{ borderColor: "var(--card-bd)", color: "var(--title-tx)" }}
            >
              <option value="Latest">Latest</option>
              <option value="Top">Top</option>
            </select>
          </label>
        </div>

        <div className="mt-3 grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
          <label className="block">
            <span className="text-[10px] font-black uppercase tracking-wider" style={{ color: "var(--muted-tx)" }}>
              Start Date
            </span>
            <input
              type="date"
              value={settings.startDate}
              max={settings.endDate || undefined}
              disabled={disabled}
              onChange={(event) => updateSetting("startDate", event.target.value)}
              className="mt-1 h-10 w-full rounded-xl border bg-white/76 px-3 text-sm font-black outline-none disabled:opacity-60 dark:bg-slate-900/40"
              style={{ borderColor: dateError ? "#fca5a5" : "var(--card-bd)", color: "var(--title-tx)" }}
            />
          </label>
          <label className="block">
            <span className="text-[10px] font-black uppercase tracking-wider" style={{ color: "var(--muted-tx)" }}>
              End Date
            </span>
            <input
              type="date"
              value={settings.endDate}
              min={settings.startDate || undefined}
              disabled={disabled}
              onChange={(event) => updateSetting("endDate", event.target.value)}
              className="mt-1 h-10 w-full rounded-xl border bg-white/76 px-3 text-sm font-black outline-none disabled:opacity-60 dark:bg-slate-900/40"
              style={{ borderColor: dateError ? "#fca5a5" : "var(--card-bd)", color: "var(--title-tx)" }}
            />
          </label>
          <label className="block">
            <span className="text-[10px] font-black uppercase tracking-wider" style={{ color: "var(--muted-tx)" }}>
              Window Days
            </span>
            <input
              type="number"
              min={1}
              value={settings.windowDays}
              disabled={disabled}
              onChange={(event) => updateSetting("windowDays", Number(event.target.value))}
              className="mt-1 h-10 w-full rounded-xl border bg-white/76 px-3 text-sm font-black outline-none disabled:opacity-60 dark:bg-slate-900/40"
              style={{ borderColor: "var(--card-bd)", color: "var(--title-tx)" }}
            />
          </label>
          <label className="block">
            <span className="text-[10px] font-black uppercase tracking-wider" style={{ color: "var(--muted-tx)" }}>
              Max Pages
            </span>
            <input
              type="number"
              min={1}
              value={settings.maxPagesPerWindow}
              disabled={disabled}
              onChange={(event) => updateSetting("maxPagesPerWindow", event.target.value)}
              placeholder="No limit"
              className="mt-1 h-10 w-full rounded-xl border bg-white/76 px-3 text-sm font-black outline-none disabled:opacity-60 dark:bg-slate-900/40"
              style={{ borderColor: "var(--card-bd)", color: "var(--title-tx)" }}
            />
          </label>
        </div>

        <div className="mt-3 grid gap-2 sm:grid-cols-3">
          {([
            ["excludeRetweets", "Exclude Retweets"],
            ["excludeReplies", "Exclude Replies"],
            ["filterByCountry", "Country Filter"],
          ] as const).map(([key, label]) => (
            <button
              key={key}
              type="button"
              disabled={disabled}
              onClick={() => updateSetting(key, !settings[key])}
              className="inline-flex h-10 items-center justify-center gap-2 rounded-xl border px-3 text-sm font-black transition disabled:opacity-60"
              style={{
                borderColor: settings[key] ? "#8b5cf6" : "var(--card-bd)",
                background: settings[key] ? "rgba(139,92,246,0.13)" : "rgba(255,255,255,0.5)",
                color: settings[key] ? "#6d28d9" : "var(--body-tx)",
              }}
            >
              <span
                className="relative inline-flex h-5 w-9 rounded-full transition"
                style={{ background: settings[key] ? "#8b5cf6" : "#cbd5e1" }}
              >
                <span
                  className="absolute top-0.5 h-4 w-4 rounded-full bg-white shadow-sm transition"
                  style={{ left: settings[key] ? "18px" : "2px" }}
                />
              </span>
              {label}
            </button>
          ))}
        </div>

        {dateError ? (
          <div className="mt-3 rounded-xl bg-red-50 px-3 py-2 text-xs font-black text-red-700">
            {dateError}
          </div>
        ) : null}
      </div>
    </div>
  );
}

function TiktokProfileControls({
  settings,
  onChange,
  disabled,
  showFollowerOptions = true,
}: {
  settings: TiktokProfileSettings | TiktokPostSettings;
  onChange: (settings: TiktokProfileSettings | TiktokPostSettings) => void;
  disabled: boolean;
  showFollowerOptions?: boolean;
}) {
  const updateMaxItems = (value: number) => {
    onChange({ ...settings, maxItems: value });
  };
  const updateProfileToggle = (key: "getFollowers" | "getFollowing", value: boolean) => {
    onChange({ ...(settings as TiktokProfileSettings), [key]: value });
  };
  return (
    <div className="mt-4 rounded-2xl border bg-white/60 p-3 dark:bg-slate-950/30" style={{ borderColor: "var(--card-bd)" }}>
      <div className="grid gap-3 sm:grid-cols-3">
        <label className="block">
          <span className="text-[10px] font-black uppercase tracking-wider" style={{ color: "var(--muted-tx)" }}>
            Max Items
          </span>
          <input
            type="number"
            min={1}
            value={settings.maxItems}
            disabled={disabled}
            onChange={(event) => updateMaxItems(Number(event.target.value))}
            className="mt-1 h-10 w-full rounded-xl border bg-white/76 px-3 text-sm font-black outline-none disabled:opacity-60 dark:bg-slate-900/40"
            style={{ borderColor: "var(--card-bd)", color: "var(--title-tx)" }}
          />
        </label>

        {showFollowerOptions
          ? ([
              ["getFollowers", "Get Followers"],
              ["getFollowing", "Get Following"],
            ] as const).map(([key, label]) => {
              const enabled = Boolean((settings as TiktokProfileSettings)[key]);

              return (
                <button
                  key={key}
                  type="button"
                  disabled={disabled}
                  onClick={() => updateProfileToggle(key, !enabled)}
                  className="mt-5 inline-flex h-10 items-center justify-center gap-2 rounded-xl border px-3 text-sm font-black transition disabled:opacity-60"
                  style={{
                    borderColor: enabled ? "#14b8a6" : "var(--card-bd)",
                    background: enabled ? "rgba(20,184,166,0.13)" : "rgba(255,255,255,0.5)",
                    color: enabled ? "#0f766e" : "var(--body-tx)",
                  }}
                >
                  <span
                    className="relative inline-flex h-5 w-9 rounded-full transition"
                    style={{ background: enabled ? "#14b8a6" : "#cbd5e1" }}
                  >
                    <span
                      className="absolute top-0.5 h-4 w-4 rounded-full bg-white shadow-sm transition"
                      style={{ left: enabled ? "18px" : "2px" }}
                    />
                  </span>
                  {label}
                </button>
              );
            })
          : null}
      </div>
    </div>
  );
}

function InstagramSection<T extends Record<string, unknown>>({
  accent,
  soft,
  title,
  description,
  usernameCount,
  entityLabel = "Accounts",
  rows,
  status,
  canRun,
  filename,
  sheetName,
  onRun,
  onReset,
  onPush,
  error,
  saveToDatabase,
  onSaveToDatabaseChange,
  showPushButton = true,
  progress,
  extraControls,
  renderTable,
}: {
  accent: string;
  soft: string;
  title: string;
  description: string;
  usernameCount: number;
  entityLabel?: string;
  rows: T[];
  status: CollectionStatus;
  canRun: boolean;
  filename: string;
  sheetName: string;
  onRun: () => void;
  onReset: () => void;
  onPush: () => void;
  error?: string | null;
  saveToDatabase?: boolean;
  onSaveToDatabaseChange?: (value: boolean) => void;
  showPushButton?: boolean;
  progress?: JobProgressLike | null;
  extraControls?: React.ReactNode;
  renderTable: () => React.ReactNode;
}) {
  const progressPercent = Math.max(0, Math.min(100, progress?.progress_percent ?? 0));

  return (
    <section
      className="overflow-hidden rounded-2xl border bg-white/78 shadow-xl backdrop-blur-xl dark:bg-slate-900/78"
      style={{ borderColor: "var(--card-bd)" }}
    >
      <div
        className="border-b p-5"
        style={{
          borderColor: "var(--card-bd)",
          background: `linear-gradient(135deg, rgba(255,255,255,0.76), ${soft})`,
        }}
      >
        <div className="flex items-start justify-between gap-4">
          <div className="flex min-w-0 items-start gap-4">
            <div className="flex h-12 w-12 shrink-0 items-center justify-center rounded-2xl text-white shadow-lg" style={{ background: accent }}>
              <DatabaseZap className="h-5 w-5" />
            </div>
            <div className="min-w-0">
              <h2 className="truncate text-xl font-black tracking-tight" style={{ color: "var(--title-tx)" }}>
                {title}
              </h2>
              <p className="mt-1 text-sm leading-6" style={{ color: "var(--muted-tx)" }}>
                {description}
              </p>
            </div>
          </div>

          <StatusPill status={status} />
        </div>

        <div className="mt-5 grid gap-3 sm:grid-cols-2">
          {[
            [entityLabel, usernameCount],
            ["Rows Ready", rows.length],
          ].map(([label, value]) => (
            <div
              key={label}
              className="rounded-2xl border bg-white/70 px-4 py-3 shadow-sm dark:bg-slate-950/35"
              style={{ borderColor: "var(--card-bd)" }}
            >
              <div className="text-[10px] font-black uppercase tracking-wider" style={{ color: "var(--muted-tx)" }}>
                {label}
              </div>
              <div className="mt-1 text-2xl font-black tracking-tight" style={{ color: "var(--title-tx)" }}>
                {value}
              </div>
            </div>
          ))}
        </div>

        <div className="mt-4 flex flex-wrap items-center gap-3">
          {onSaveToDatabaseChange ? (
            <button
              type="button"
              onClick={() => onSaveToDatabaseChange(!saveToDatabase)}
              className="inline-flex h-10 items-center gap-2 rounded-full border px-4 text-sm font-black transition"
              style={{
                borderColor: saveToDatabase ? "#10b981" : "var(--card-bd)",
                background: saveToDatabase ? "rgba(16,185,129,0.13)" : "rgba(255,255,255,0.5)",
                color: saveToDatabase ? "#047857" : "var(--body-tx)",
              }}
            >
              <span
                className="relative inline-flex h-5 w-9 rounded-full transition"
                style={{ background: saveToDatabase ? "#10b981" : "#cbd5e1" }}
              >
                <span
                  className="absolute top-0.5 h-4 w-4 rounded-full bg-white shadow-sm transition"
                  style={{ left: saveToDatabase ? "18px" : "2px" }}
                />
              </span>
              Save to DB
            </button>
          ) : null}
          <button
            type="button"
            onClick={onRun}
            disabled={!canRun || status === "running"}
            className="inline-flex h-10 items-center gap-2 rounded-full px-5 text-sm font-black text-white shadow-lg transition disabled:cursor-not-allowed disabled:opacity-50"
            style={{ background: accent, boxShadow: `0 14px 28px ${soft}` }}
          >
            {status === "running" ? <Loader2 className="h-4 w-4 animate-spin" /> : <Play className="h-4 w-4" />}
            Run
          </button>
          <button
            type="button"
            onClick={onReset}
            className="inline-flex h-10 items-center gap-2 rounded-full border bg-white/50 px-4 text-sm font-black transition hover:bg-white/75"
            style={{ borderColor: "var(--card-bd)", color: "var(--body-tx)" }}
          >
            <RefreshCw className="h-4 w-4" />
            Reset
          </button>
          <ExportExcelButton rows={rows} filename={filename} sheetName={sheetName} />
          {showPushButton ? (
            <button
              type="button"
              onClick={onPush}
              disabled={!rows.length || status === "running" || status === "pushed"}
              className="inline-flex h-10 items-center gap-2 rounded-full bg-slate-900 px-4 text-sm font-black text-white shadow-lg shadow-slate-900/15 transition hover:bg-slate-800 disabled:cursor-not-allowed disabled:opacity-45 dark:bg-white dark:text-slate-950"
            >
              <UploadCloud className="h-4 w-4" />
              {status === "pushed" ? "Pushed" : "Push DB"}
            </button>
          ) : null}
        </div>

        {extraControls}

        {error ? (
          <div className="mt-4 rounded-xl border border-red-200 bg-red-50 px-4 py-3 text-sm font-bold text-red-700">
            {error}
          </div>
        ) : null}

        {progress ? (
          <div className="mt-4 rounded-2xl border bg-white/70 p-4 shadow-sm dark:bg-slate-950/35" style={{ borderColor: "var(--card-bd)" }}>
            <div className="flex flex-wrap items-center justify-between gap-3">
              <div>
                <div className="text-[10px] font-black uppercase tracking-wider" style={{ color: "var(--muted-tx)" }}>
                  Job {progress.job_id ? progress.job_id.slice(0, 8) : ""}
                </div>
                <div className="mt-1 text-sm font-black capitalize" style={{ color: "var(--title-tx)" }}>
                  {progress.status}
                  {progress.current_username
                    ? ` · @${progress.current_username}`
                    : progress.current_keyword
                      ? ` · ${progress.current_keyword}`
                      : progress.current_profile
                        ? ` · ${progress.current_profile}`
                        : progress.current_profile_url
                          ? ` · ${progress.current_profile_url}`
                          : progress.current_target_url
                            ? ` · ${progress.current_target_url}`
                        : progress.current_url
                          ? ` · ${progress.current_url}`
                          : ""}
                </div>
              </div>
              <div className="text-right text-sm font-black" style={{ color: "var(--title-tx)" }}>
                {progress.completed ?? 0}/{progress.total ?? 0}
              </div>
            </div>
            <div className="mt-3 h-2 overflow-hidden rounded-full bg-slate-200/80 dark:bg-slate-800">
              <div
                className="h-full rounded-full bg-emerald-500 transition-all"
                style={{ width: `${progressPercent}%` }}
              />
            </div>
            <div className="mt-2 flex justify-between text-xs font-bold" style={{ color: "var(--muted-tx)" }}>
              <span>{progress.successful ?? 0} successful</span>
              <span>{progress.failed ?? 0} failed</span>
              <span>{progressPercent.toFixed(0)}%</span>
            </div>
            {typeof progress.scraped_posts === "number" ||
            typeof progress.images_uploaded === "number" ||
            typeof progress.images_skipped === "number" ||
            typeof progress.images_failed === "number" ? (
              <div className="mt-3 grid gap-2 text-xs font-black sm:grid-cols-4" style={{ color: "var(--body-tx)" }}>
                <span className="rounded-lg bg-white/60 px-2 py-1 dark:bg-slate-900/50">
                  Posts {formatNumber(progress.scraped_posts ?? 0)}
                </span>
                <span className="rounded-lg bg-white/60 px-2 py-1 dark:bg-slate-900/50">
                  Uploaded {formatNumber(progress.images_uploaded ?? 0)}
                </span>
                <span className="rounded-lg bg-white/60 px-2 py-1 dark:bg-slate-900/50">
                  Skipped {formatNumber(progress.images_skipped ?? 0)}
                </span>
                <span className="rounded-lg bg-white/60 px-2 py-1 dark:bg-slate-900/50">
                  Failed {formatNumber(progress.images_failed ?? 0)}
                </span>
              </div>
            ) : null}
          </div>
        ) : null}
      </div>

      <div className="p-5">
        <div className="mb-4 flex items-center justify-between gap-4">
          <div>
            <div className="text-xs font-black uppercase tracking-wider" style={{ color: "var(--muted-tx)" }}>
              Data Preview
            </div>
            <div className="mt-1 text-sm font-bold" style={{ color: "var(--title-tx)" }}>
              {rows.length ? `${formatNumber(rows.length)} rows collected` : "Waiting for collection run"}
            </div>
          </div>
        </div>
        {renderTable()}
      </div>
    </section>
  );
}

function DataTable<T>({
  rows,
  headers,
  emptyMessage,
  renderRow,
}: {
  rows: T[];
  headers: string[];
  emptyMessage: string;
  renderRow: (row: T) => Array<string | number | boolean>;
}) {
  return (
    <div className="overflow-hidden rounded-2xl border bg-white/55 shadow-sm dark:bg-slate-950/30" style={{ borderColor: "var(--card-bd)" }}>
      <div className="max-h-[320px] overflow-auto custom-scroll">
        <table className="w-full min-w-[1040px] border-collapse text-left text-sm">
          <thead className="sticky top-0 z-[1] bg-white/88 backdrop-blur-xl dark:bg-slate-900/90">
            <tr style={{ color: "var(--muted-tx)" }}>
              {headers.map((head) => (
                <th key={head} className="px-4 py-3 text-xs font-black uppercase tracking-wider">{head}</th>
              ))}
            </tr>
          </thead>
          <tbody>
            {rows.length === 0 ? (
              <tr>
                <td colSpan={headers.length} className="px-4 py-14 text-center text-sm" style={{ color: "var(--muted-tx)" }}>
                  {emptyMessage}
                </td>
              </tr>
            ) : (
              rows.map((row, rowIndex) => (
                <tr key={rowIndex} className="border-t" style={{ borderColor: "var(--card-bd)", color: "var(--body-tx)" }}>
                  {renderRow(row).map((cell, cellIndex) => (
                    <td key={cellIndex} className="max-w-[220px] truncate px-4 py-3">
                      {String(cell)}
                    </td>
                  ))}
                </tr>
              ))
            )}
          </tbody>
        </table>
      </div>
    </div>
  );
}

export default function DataCollectionPlatformPage({ platformKey }: { platformKey: PlatformKey }) {
  if (platformKey === "instagram") {
    return <InstagramCollectionPage />;
  }

  if (platformKey === "twitter") {
    return <TwitterCollectionPage />;
  }

  if (platformKey === "tiktok") {
    return <TiktokCollectionPage />;
  }

  return <GenericDataCollectionPlatformPage platformKey={platformKey} />;
}

function GenericDataCollectionPlatformPage({ platformKey }: { platformKey: Exclude<PlatformKey, "instagram" | "twitter" | "tiktok"> }) {
  const platform = PLATFORM_CONFIG[platformKey];
  const [usernames, setUsernames] = useState("");
  const [profileDraft, setProfileDraft] = useState("");
  const [country, setCountry] = useState("");
  const [project, setProject] = useState("");
  const [saveToDatabase, setSaveToDatabase] = useState(true);
  const [savePostsToDatabase, setSavePostsToDatabase] = useState(true);
  const [showSaveConfirm, setShowSaveConfirm] = useState(false);
  const [showPostSaveConfirm, setShowPostSaveConfirm] = useState(false);
  const [activeCollection, setActiveCollection] = useState<"profile" | "posts">("profile");
  const [status, setStatus] = useState<CollectionStatus>("idle");
  const [postStatus, setPostStatus] = useState<CollectionStatus>("idle");
  const [rows, setRows] = useState<LinkedinProfileScrapeRow[]>([]);
  const [postRows, setPostRows] = useState<LinkedinPostScrapeRow[]>([]);
  const [progress, setProgress] = useState<LinkedinProfileJobProgress | null>(null);
  const [postProgress, setPostProgress] = useState<LinkedinPostJobProgress | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [postError, setPostError] = useState<string | null>(null);
  const [postSettings, setPostSettings] = useState<LinkedinPostSettings>({
    startDate: "2026-04-01",
    endDate: getTodayDateInputValue(),
    maxPosts: 100000,
  });

  const profileUrls = useMemo(() => Array.from(new Set(parseListValues(usernames))), [usernames]);
  const usernameCount = profileUrls.length;
  const canRunProfile = Boolean(usernameCount && country.trim() && project.trim());
  const postDateError = postSettings.startDate && postSettings.endDate && postSettings.endDate < postSettings.startDate
    ? "End date must be on or after start date."
    : null;
  const canRunPosts = Boolean(usernameCount && postSettings.startDate && postSettings.endDate && postSettings.maxPosts > 0 && !postDateError);
  const canRun = canRunProfile || canRunPosts;

  const updateProfileUrls = (urls: string[]) => {
    setUsernames(Array.from(new Set(urls)).join("\n"));
    if (status !== "running") setStatus(rows.length ? "ready" : "idle");
    if (postStatus !== "running") setPostStatus(postRows.length ? "ready" : "idle");
  };
  const addDraftProfiles = (value = profileDraft) => {
    const next = parseListValues(value);
    if (!next.length) return;
    updateProfileUrls([...profileUrls, ...next]);
    setProfileDraft("");
  };
  const executeCollection = async (shouldSave = saveToDatabase) => {
    setStatus("running");
    setError(null);
    setProgress(null);
    try {
      const result = await scrapeLinkedinProfiles(
        {
          profile_urls: profileUrls,
          country: country.trim(),
          project: project.trim(),
          save_to_database: shouldSave,
        },
        (nextProgress) => {
          setProgress(nextProgress);
          if (nextProgress.profiles?.length) setRows(nextProgress.profiles);
        }
      );
      setRows(result.profiles);
      setStatus(result.saved_to_database ? "pushed" : "ready");
    } catch (collectionError) {
      setStatus("idle");
      setError(collectionError instanceof Error ? collectionError.message : "Failed to collect LinkedIn profiles");
    }
  };
  const handleRun = () => {
    if (!canRunProfile || status === "running") return;
    if (saveToDatabase) {
      setShowSaveConfirm(true);
      return;
    }
    void executeCollection(false);
  };

  const executePostCollection = async (shouldSave = savePostsToDatabase) => {
    if (postDateError) {
      setPostError(postDateError);
      return;
    }
    setPostStatus("running");
    setPostError(null);
    setPostProgress(null);
    try {
      const result = await scrapeLinkedinPosts(
        {
          target_urls: profileUrls,
          start_date: postSettings.startDate,
          end_date: postSettings.endDate,
          max_posts: postSettings.maxPosts,
          save_to_database: shouldSave,
        },
        (nextProgress) => {
          setPostProgress(nextProgress);
          if (nextProgress.posts?.length) setPostRows(nextProgress.posts);
        }
      );
      setPostRows(result.posts);
      setPostStatus(result.saved_to_database ? "pushed" : "ready");
    } catch (collectionError) {
      setPostStatus("idle");
      setPostError(collectionError instanceof Error ? collectionError.message : "Failed to collect LinkedIn posts");
    }
  };
  const runPostCollection = () => {
    if (!canRunPosts || postStatus === "running") return;
    if (savePostsToDatabase) {
      setShowPostSaveConfirm(true);
      return;
    }
    void executePostCollection(false);
  };

  const handleReset = () => {
    setRows([]);
    setStatus("idle");
    setProgress(null);
    setError(null);
  };
  const resetPosts = () => {
    setPostRows([]);
    setPostStatus("idle");
    setPostProgress(null);
    setPostError(null);
  };

  return (
    <main className="min-h-screen">
      <DashboardTopbar title="Internal Data Collection" />

      <div className="space-y-6 p-8">
        <section className="overflow-hidden rounded-2xl border p-6 shadow-xl backdrop-blur-xl" style={{ borderColor: platform.soft, background: "linear-gradient(135deg, rgba(255,255,255,0.92), rgba(239,246,255,0.86) 45%, rgba(224,242,254,0.82))" }}>
          <div className="flex flex-wrap items-center justify-between gap-6">
            <div className="flex min-w-0 items-start gap-4">
              <div className="flex h-14 w-14 shrink-0 items-center justify-center rounded-2xl bg-[#0a66c2] text-white shadow-xl shadow-blue-500/20">
                <Linkedin className="h-7 w-7" />
              </div>
              <div className="min-w-0">
                <div className="inline-flex rounded-full bg-white/70 px-3 py-1 text-xs font-black uppercase tracking-[0.18em] text-[#0a66c2] shadow-sm">LinkedIn Workspace</div>
                <h1 className="mt-3 text-3xl font-black tracking-tight" style={{ color: "var(--title-tx)" }}>Collection Studio</h1>
                <p className="mt-2 max-w-3xl text-sm leading-6" style={{ color: "var(--muted-tx)" }}>Use one shared batch setup, then run profile and posts collection as separate reviewable outputs.</p>
              </div>
            </div>
            <div className="grid min-w-[420px] gap-3 sm:grid-cols-3">
              {[["Companies", usernameCount, "from input"], ["Profiles", rows.length, "ready rows"], ["Posts", postRows.length, "ready rows"]].map(([label, value, caption]) => (
                <div key={label} className="rounded-2xl border bg-white/70 px-5 py-4 shadow-sm backdrop-blur-xl" style={{ borderColor: "var(--card-bd)" }}>
                  <div className="text-[10px] font-black uppercase tracking-wider" style={{ color: "var(--muted-tx)" }}>{label}</div>
                  <div className="mt-1 text-3xl font-black tracking-tight" style={{ color: "var(--title-tx)" }}>{value}</div>
                  <div className="mt-1 text-[11px] font-bold text-[#0a66c2]">{caption}</div>
                </div>
              ))}
            </div>
          </div>
        </section>

        <section className="rounded-2xl border bg-white/78 p-5 shadow-lg backdrop-blur-xl dark:bg-slate-900/78" style={{ borderColor: "var(--card-bd)" }}>
          <div className="grid gap-5 xl:grid-cols-[minmax(420px,1.05fr)_0.95fr]">
            <div className="rounded-2xl border p-5 shadow-sm" style={{ borderColor: platform.soft, background: "linear-gradient(135deg, rgba(255,255,255,0.9), rgba(239,246,255,0.68))" }}>
              <div className="flex flex-wrap items-start justify-between gap-4">
                <div>
                  <h2 className="text-2xl font-black tracking-tight" style={{ color: "var(--title-tx)" }}>Batch Setup</h2>
                  <p className="mt-1 text-sm leading-6" style={{ color: "var(--muted-tx)" }}>Add LinkedIn company URLs once, then use the same batch for profile and posts collection.</p>
                </div>
                <span className="inline-flex h-9 items-center rounded-full px-4 text-xs font-black uppercase tracking-wider text-white shadow-lg" style={{ background: canRun ? "#10b981" : "#94a3b8" }}>{canRun ? "Ready" : "Needs input"}</span>
              </div>
              <div className="mt-5 rounded-2xl border bg-white/76 p-4 shadow-inner dark:bg-slate-950/25" style={{ borderColor: "var(--card-bd)" }}>
                <div className="flex items-center justify-between gap-4">
                  <label className="inline-flex items-center gap-2 text-xs font-black uppercase tracking-[0.18em] text-[#0a66c2]"><Linkedin className="h-4 w-4" />Source Companies</label>
                  {usernameCount ? <button type="button" onClick={() => updateProfileUrls([])} className="rounded-full bg-slate-100 px-3 py-1 text-xs font-black text-slate-500">Clear all</button> : <span className="rounded-full bg-blue-500/10 px-3 py-1 text-xs font-black text-[#0a66c2]">Empty</span>}
                </div>
                <div className="mt-4 flex gap-3">
                  <div className="flex min-w-0 flex-1 items-center rounded-xl border bg-white/82 px-4 shadow-sm focus-within:border-blue-400 focus-within:ring-4 focus-within:ring-blue-500/10" style={{ borderColor: "var(--card-bd)" }}>
                    <Linkedin className="mr-2 h-5 w-5 shrink-0 text-[#0a66c2]" />
                    <input value={profileDraft} onChange={(event) => setProfileDraft(event.target.value)} onKeyDown={(event) => { if (event.key === "Enter" || event.key === ",") { event.preventDefault(); addDraftProfiles(); } }} onPaste={(event) => { const pasted = event.clipboardData.getData("text"); if (/[\n,]/.test(pasted)) { event.preventDefault(); addDraftProfiles(`${profileDraft}\n${pasted}`); } }} placeholder="paste company URL and press Enter" className="h-12 min-w-0 flex-1 border-0 bg-transparent text-sm font-black outline-none placeholder:text-slate-400" style={{ color: "var(--title-tx)" }} />
                  </div>
                  <button type="button" onClick={() => addDraftProfiles()} disabled={!parseListValues(profileDraft).length} className="inline-flex h-12 items-center gap-2 rounded-xl bg-[#0a66c2] px-5 text-sm font-black text-white shadow-lg shadow-blue-500/20 disabled:opacity-45"><Plus className="h-4 w-4" />Add</button>
                </div>
                <div className="mt-4 min-h-36 rounded-xl border border-dashed bg-white/54 p-3" style={{ borderColor: platform.soft }}>
                  {profileUrls.length ? <div className="flex flex-wrap gap-2">{profileUrls.map((url) => <span key={url} className="inline-flex h-9 max-w-full items-center gap-2 rounded-full border bg-white px-3 text-sm font-black shadow-sm" style={{ borderColor: "var(--card-bd)", color: "var(--title-tx)" }}><span className="max-w-[320px] truncate">{url}</span><button type="button" onClick={() => updateProfileUrls(profileUrls.filter((item) => item !== url))} className="inline-flex h-5 w-5 items-center justify-center rounded-full bg-blue-50 text-[#0a66c2]" aria-label={`Remove ${url}`}><X className="h-3.5 w-3.5" /></button></span>)}</div> : <div className="flex h-28 items-center justify-center text-center text-sm font-bold" style={{ color: "var(--muted-tx)" }}>Add company URLs one by one, or paste a comma-separated list.</div>}
                </div>
              </div>
            </div>
            <div className="rounded-2xl border bg-white/72 p-5 shadow-sm backdrop-blur-xl dark:bg-slate-950/30" style={{ borderColor: "var(--card-bd)" }}>
              <div className="flex items-center justify-between gap-4">
                <div><div className="text-xs font-black uppercase tracking-[0.22em]" style={{ color: "var(--muted-tx)" }}>Batch Details</div><h3 className="mt-1 text-xl font-black tracking-tight" style={{ color: "var(--title-tx)" }}>Output Metadata</h3></div>
                <div className="flex h-11 w-11 items-center justify-center rounded-xl bg-slate-900 text-white shadow-lg"><FileSpreadsheet className="h-5 w-5" /></div>
              </div>
              <div className="mt-5 grid gap-3">
                {[["Country", country, setCountry, "UAE"], ["Project", project, setProject, "realestate_dbh"]].map(([label, value, setter, placeholder]) => <label key={label as string} className="block rounded-2xl border bg-white/68 px-4 py-3 focus-within:border-blue-400 focus-within:ring-4 focus-within:ring-blue-500/10" style={{ borderColor: "var(--card-bd)" }}><span className="text-[10px] font-black uppercase tracking-wider" style={{ color: "var(--muted-tx)" }}>{label as string}</span><input value={value as string} onChange={(event) => (setter as (value: string) => void)(event.target.value)} placeholder={placeholder as string} className="mt-1 h-8 w-full border-0 bg-transparent p-0 text-base font-black outline-none" style={{ color: "var(--title-tx)" }} /></label>)}
              </div>
              <div className="mt-4 rounded-2xl border bg-gradient-to-r from-blue-500/10 to-cyan-400/10 px-4 py-3" style={{ borderColor: platform.soft }}><div className="text-xs font-bold leading-5" style={{ color: "var(--muted-tx)" }}>These values are attached to every collected company profile.</div></div>
            </div>
          </div>
        </section>

        <section className="rounded-2xl border bg-white/70 p-4 shadow-lg backdrop-blur-xl dark:bg-slate-900/70" style={{ borderColor: "var(--card-bd)" }}>
          <div className="mb-4 inline-flex rounded-2xl border bg-white/72 p-1 shadow-sm" style={{ borderColor: "var(--card-bd)" }}>
            {[["profile", "Profile Data", rows.length, platform.accent], ["posts", "Posts Data", postRows.length, "#8b5cf6"]].map(([key, label, count, accent]) => {
              const selected = activeCollection === key;
              return <button key={key} type="button" onClick={() => setActiveCollection(key as "profile" | "posts")} className="inline-flex h-11 items-center gap-3 rounded-xl px-4 text-sm font-black transition" style={{ background: selected ? accent as string : "transparent", color: selected ? "#fff" : "var(--muted-tx)", boxShadow: selected ? `0 12px 26px ${key === "profile" ? platform.soft : "rgba(139,92,246,0.18)"}` : "none" }}>{label}<span className="inline-flex min-w-7 justify-center rounded-full px-2 py-0.5 text-xs" style={{ background: selected ? "rgba(255,255,255,0.22)" : "rgba(100,116,139,0.12)", color: selected ? "#fff" : "var(--body-tx)" }}>{count}</span></button>;
            })}
          </div>
          {activeCollection === "profile" ? (
            <InstagramSection accent={platform.accent} soft={platform.soft} title="Profile Data" description="Company metadata, industry, employee and follower counts, location, description, and project." usernameCount={usernameCount} entityLabel="Companies" rows={rows} status={status} canRun={canRunProfile} filename="linkedin_profile_data_collection" sheetName="LinkedIn Profiles" onRun={handleRun} onReset={handleReset} onPush={() => setStatus("pushed")} error={error} saveToDatabase={saveToDatabase} onSaveToDatabaseChange={setSaveToDatabase} showPushButton={false} progress={progress} renderTable={() => <DataTable rows={rows} emptyMessage="No LinkedIn profile data yet. Add company URLs and run profile collection." headers={["Company", "LinkedIn URL", "Website", "Industry", "Employees", "Followers", "Universal Name", "Tagline", "Hashtag", "Country", "City", "Postal Code", "Founded", "Description", "Project", "Last Updated"]} renderRow={(row) => [row.company_name, row.url, row.website_url ?? "", row.industry ?? "", formatNumber(row.employee_count || 0), formatNumber(row.follower_count || 0), row.universal_name ?? "", row.tagline ?? "", row.hashtag ?? "", row.country ?? "", row.city ?? "", row.postal_code ?? "", row.founded_on ?? "", row.description ?? "", row.project ?? "", new Date(row.last_updated).toLocaleString()]} />}/>
          ) : (
            <InstagramSection accent="#8b5cf6" soft="rgba(139,92,246,0.16)" title="Posts Data" description="LinkedIn company posts collected within the selected date range." usernameCount={usernameCount} entityLabel="Companies" rows={postRows} status={postStatus} canRun={canRunPosts} filename="linkedin_posts_data_collection" sheetName="LinkedIn Posts" onRun={runPostCollection} onReset={resetPosts} onPush={() => setPostStatus("pushed")} error={postError} saveToDatabase={savePostsToDatabase} onSaveToDatabaseChange={setSavePostsToDatabase} showPushButton={false} progress={postProgress} extraControls={<LinkedinPostControls settings={postSettings} onChange={setPostSettings} disabled={postStatus === "running"} dateError={postDateError} />} renderTable={() => <DataTable rows={postRows} emptyMessage="No LinkedIn posts yet. Add company URLs and run posts collection." headers={["Company", "Universal Name", "Post Text", "Post URL", "Uploaded At", "Likes", "Shares", "Comments", "Last Updated"]} renderRow={(row) => [row.source_company ?? "", row.universal_name ?? "", row.post_text ?? "", row.post_url, new Date(row.uploaded_at).toLocaleString(), formatNumber(row.likes || 0), formatNumber(row.shares || 0), formatNumber(row.comments || 0), new Date(row.last_updated).toLocaleString()]} />}/>
          )}
        </section>
      </div>
      {showSaveConfirm ? <SaveToDatabaseConfirmModal collectionName="LinkedIn profiles" usernameCount={usernameCount} project={project} onCancel={() => setShowSaveConfirm(false)} onRunPreviewOnly={() => { setShowSaveConfirm(false); setSaveToDatabase(false); void executeCollection(false); }} onConfirm={() => { setShowSaveConfirm(false); void executeCollection(true); }} /> : null}
      {showPostSaveConfirm ? <SaveToDatabaseConfirmModal collectionName="LinkedIn posts" usernameCount={usernameCount} project={`${postSettings.startDate} to ${postSettings.endDate}`} onCancel={() => setShowPostSaveConfirm(false)} onRunPreviewOnly={() => { setShowPostSaveConfirm(false); setSavePostsToDatabase(false); void executePostCollection(false); }} onConfirm={() => { setShowPostSaveConfirm(false); void executePostCollection(true); }} /> : null}
    </main>
  );
}
