# Trend Object — Field Reference

Every field on a row of `food_intel.trends`: what it means, and exactly how it is
computed.

**The dividing line in this table:** a language model authors the words (`name`,
`narrative.summary`, `narrative.opportunity_summary`); arithmetic authors every
number. No model is ever asked to produce a count, a percentage or an index. The
`interpret` stage is handed already-computed numbers and writes prose about
them — it cannot invent them.

Source of truth: `app/trends/metrics.py` (all numbers), `app/trends/run.py`
(stage orchestration), `app/trends/store.py` (persistence).

---

## Top-level columns

| Field | Type | Meaning | How it is computed |
|---|---|---|---|
| `trend_id` | text | Primary key. | Micro: `slugify(name)` + `--` + first 8 chars of `run_id`. Umbrella: `u-` + slug + `--` + run prefix. A slug collision within a run gets the cluster label appended. |
| `run_id` | text | Which pipeline run produced this row. | The `--run-id` argument, or `{cohort}-{UTC timestamp}`. Re-running a run id deletes and rewrites its rows. |
| `level` | text | `micro` or `umbrella`. | `micro` = one HDBSCAN cluster. `umbrella` = a group of micro trends. |
| `parent_trend_id` | text | The umbrella this micro trend belongs to. | Set when umbrellas are built; `null` on umbrella rows themselves. |
| `name` | text | Human-readable trend name. | **LLM-authored** in the `name` stage from the 25 most central × engaged captions, the top 10 hashtags and the cluster's c-TF-IDF keywords. |
| `quadrant` | text | Strategic bucket. | Derived from the two indices — see [Quadrant](#quadrant) below. |
| `volume_index` | real 0–100 | How large this trend is *relative to its peers*. | Percentile rank of `metrics.volume_raw` among rows of the same `level`. Ties share their average rank. |
| `growth_index` | real 0–100 | How fast it is growing *relative to its peers*. | Percentile rank of `metrics.growth_pct` among rows of the same `level`. Trends with an unmeasurable rate rank above every measurable one. **This is the sort key.** |
| `post_count` | integer | Member posts in this trend. | Count of every post assigned to it — community members plus brand/influencer posts that passed the belonging gate. |
| `unique_authors` | integer | Distinct creators. | Size of the set of `author_username` across member posts. |
| `narrative` | jsonb | The written layer. | See [narrative](#narrative). |
| `metrics` | jsonb | The raw numbers behind the indices. | See [metrics](#metrics). |
| `timeline` | jsonb | Weekly series. | See [timeline](#timeline). |
| `example_posts` | jsonb | Showcase posts. | See [example_posts](#example_posts). |
| `member_posts` | jsonb | Full membership list. | `[{platform, post_id, source, posted_at}]` for every member — the audit trail for `post_count`, and what the detail page's date-range filter recomputes from. |
| `created_at` | timestamptz | Row write time. | Database default. |

---

## `narrative`

| Key | Meaning | How it is computed |
|---|---|---|
| `summary` | One-paragraph description. | **LLM-authored** during `name`. |
| `opportunity_summary` | The commercial "so what". | **LLM-authored** during `interpret`, from this row's already-computed metrics. The prompt requires it to call a null rate "new" and to treat thousands-of-percent growth as a recent surge, not a reliable rate. |
| `related_themes` | Adjacent themes. | LLM-authored during `name`. Empty on umbrellas. |
| `product_entities` | Named dishes, products, brands. | LLM-authored during `name`. Empty on umbrellas. |
| `keywords` | Distinctive terms. | **Not LLM.** c-TF-IDF from BERTopic — terms frequent in this cluster and rare elsewhere. |
| `naming_confidence` | Model's confidence in the name. | Returned by the naming call. `null` on umbrellas. |
| `member_trend_ids` | Micro trends under this umbrella. | Umbrella rows only. |

---

## `metrics`

| Key | Meaning | How it is computed |
|---|---|---|
| `volume_raw` | Posts in the **last 90 days**. | Count where `posted_at > as_of − 90 days`. This, not `post_count`, is what `volume_index` ranks — so a large but dormant trend does not outrank a smaller live one. |
| `growth_pct` | Change in share of the conversation. | Share-of-voice ratio between the two 56-day windows, smoothed, floored at −100%. Always defined. See [Growth](#growth-definition-computation-and-how-to-read-it). |
| `recent_posts` | Posts in the recent window. | The numerator, published so the change can be read as counts. |
| `previous_posts` | Posts in the previous window. | The denominator. Below 10 the percentage is not trustworthy. |
| `first_post` | Earliest member post. | Minimum `posted_at`. |
| `is_new` | Did the trend exist before? | `first_post` falls inside the recent window. |
| `months` | Calendar-month series. | `[{month, post_count, engagement, unique_authors}]` — drives the month filter, since ISO weeks straddle month boundaries. |
| `engagement_total` | Total engagement. | Sum of `engagement_total` (likes + comments + shares) across member posts. |
| `platform_mix` | Posts per platform. | `{instagram: n, tiktok: n}`. |
| `source_mix` | Posts per source. | `{community: n, brand: n, influencer: n}`. |
| `as_of` | Anchor date for every window above. | The **latest `posted_at` in the corpus**, not today's date. Windows are relative to the data, so a stale scrape does not make every trend look dead. |

### Growth: definition, computation and how to read it

**What it measures.** Whether a trend is taking a larger or smaller share of the
conversation than it was — not whether its raw post count went up.

```
recent   = posts in the 56 days up to as_of
previous = posts in the 56 days before that
pad      = 5                       (smoothing, GROWTH_SMOOTHING)
N        = trends at this level

share_recent   = (recent   + pad) / (total_recent   + pad x N)
share_previous = (previous + pad) / (total_previous + pad x N)

growth_pct = (share_recent / share_previous - 1) x 100     floored at -100%
```

`total_recent` and `total_previous` are the level's whole volume, so growth is
computed once per level rather than per trend.

**Why share and not raw volume.** Raw volume measured the scrape. Between the
two windows in this corpus the total post count grew **4.1x**, so every trend
inherited that multiplier and the leaderboard read 22,300%, 20,700%, 14,000% —
all of it collection artefact. Dividing each side by its own window's total
cancels the common factor, leaving only movement relative to everything else.

| Trend | prev -> recent | Raw ratio | Share of voice |
|---|---|---|---|
| Wedding Cakes | 2 -> 448 | 22,300% | 1,640% |
| Father's Day Cakes | 1 -> 208 | 20,700% | 854% |
| Birthday Cakes | 1 -> 99 | 9,800% | 366% |

**Why smoothing.** Adding 5 posts to both sides stops a baseline of one post
from setting the denominator, and makes the value **always defined** — there is
no divide-by-zero, so no sentinel and no "unmeasurable" state. A trend going
0 -> 386 posts gets a finite, comparable number.

**What it now reveals.** Across the current run growth spans -88% to +2,420%,
and **57 of 88 trends are losing share** (median -46%). The raw ratio hid that
completely by showing almost everything as explosive growth. Juices and
Smoothies fell 77 -> 31 posts: a real decline the old metric would have
reported as growth had the corpus expanded around it.

**Reading it.** `growth_index` (0-100) is the percentile of `growth_pct` within
the level and is the **sort key** and the headline the UI shows. `recent_posts`
and `previous_posts` are published so a reader can judge the baseline: a rate
resting on fewer than ~10 prior posts is directional at best, which is why the
card shows the post change rather than the percentage.

**How to make it better**, in order of value:

1. **Scrape continuously.** Share of voice removes the common inflation, but
   equal windows only compare like with like when collection is even. This is
   still the single biggest improvement available.
2. **Widen the windows** beyond 56 days. More posts per side means less swing
   from a handful of posts.
3. **Tune `GROWTH_SMOOTHING`** as volume grows. 5 suits a corpus where the
   median baseline is 17 posts; denser data wants less padding.

---

## `is_new`

True when the trend's **first post falls inside the recent window** — it did not
exist before. This is deliberately not the same as "the previous window was
empty": a trend can have posts back to 2023 and still be silent for one 56-day
stretch. Under the earlier, looser definition three trends dating from 2023 and
2024 were badged "New"; under this one, none of the 88 are new.

---

## `timeline`

An array of weekly points, oldest first. Weeks start on Monday
(`week_start` is the ISO date of that Monday).

| Key | Meaning | How it is computed |
|---|---|---|
| `week_start` | Monday of the week. | `posted_at − weekday(posted_at)`. |
| `post_count` | Posts that week. | Count of member posts. Drives the **Social Trendline**. |
| `engagement` | Engagement that week. | Sum of member post engagement. Drives the **Engagement Trendline**. |
| `unique_authors` | Distinct creators that week. | Size of the author set for that week. |

---

## `example_posts`

| Key | Meaning |
|---|---|
| `top` | Up to 6 showcase posts across all sources. |
| `by_source` | Up to 3 posts each for `community`, `brand`, `influencer` — the three UI columns. |

Each entry carries `platform`, `post_id`, `source`, `author`, `caption` (first
280 chars), `post_url`, `engagement`, `likes`, `comments`, `views`, `media_key`.

**How examples are chosen.** Posts that mention a topical term are ranked by
engagement first; if fewer than `k` qualify, the most-engaging remainder fills
the gap. Topical terms come from the trend's keywords, product entities and the
words of its name, minus generic filler ("varieties", "experiences", "recipes").

Ranking on engagement alone surfaced whatever went viral inside a cluster, which
is frequently its least typical post. Centrality was tried and rejected: in a
noisy cluster the centroid describes the noise, so its correlation with topical
relevance is weak and sometimes inverted.

`media_key` is the **first** image key of the post, resolved to a presigned S3
URL. A bare key lives in `trends-media-bucket`; a key written as
`s3://bucket/key` names its own bucket, which is how the tracked brand and
influencer posts serve images the account crawl left in `raw-data-bucket` —
99.6% of their food posts have one there, and nothing was copied to make that
work.

`TREND_USE_THUMBNAILS` rewrites bare keys to `thumb/<key>.webp` (~21 KB against
a ~254 KB mean, a 12.3x saving). **It is off**, because the backfill has reached
only 40% of the corpus and a post with no generated thumbnail renders blank even
though the original exists — measured at 400 sampled community posts, 100% had
the full-size image and 40% had a thumbnail, so turning it on blanked roughly
60% of consumer cards. Turn it on when the backfill has actually covered the
corpus, not before. Foreign-bucket keys are always served full size.

---

## Quadrant

Both axes are percentile ranks within the row's own level, so the split is
always at the median of that level — the quadrant is a statement about a trend's
standing among its peers, never an absolute threshold.

| | Growth index < 50 | Growth index ≥ 50 |
|---|---|---|
| **Volume index ≥ 50** | `mainstream` — big, steady | `slow-burner` — big and still climbing |
| **Volume index < 50** | `watchlist` — small, flat | `breakthrough` — small but climbing fast |

---

## What is counted, and what never reaches these fields

Trends are **discovered** from community posts only. Brand and influencer posts
are **assigned** to trends that already exist; they can never create one.

### What "brand" and "influencer" mean

A post counts as **brand** or **influencer** only when its author is an account
we track — the lists in `instagram_profile` under projects `food_trends_brands`
(10 accounts with data) and `food_trends_influencers` (30 accounts). Everything
else in the corpus is **community**, whoever wrote it.

Each corpus stays in the table that owns it, and the pipeline reads one view
across them:

```
public.community_posts   the community scrape, dumped from the other database
public.instagram_posts   the tracked accounts, keyed by instagram_profile
food_intel.post_food     this pipeline's food verdict, for posts from either
        │
        └─► food_intel.trend_posts   the view every stage and endpoint reads
```

`source` is **derived** in the view by looking the author up in the tracked
lists, so it is a fact checkable at query time rather than a label written in at
load time. That distinction is the whole point: the previous design copied
brand and influencer posts into `community_posts` along with a `source` string,
and once a post sits in the community table with a text field claiming it is a
brand, nothing can verify the claim — which is exactly how 16,887 keyword hits
came to occupy the brand column.

This is narrower than it used to be, and deliberately so. The corpus was built
by two opposite methods: the tracked accounts were crawled by account, and
everything else was collected by keyword search. The keyword scrape carried its
own `source` field — `Brand`, `Influencer`, `Community` — and the ETL copied it
verbatim, which put 16,887 posts in the brand and influencer columns on the
strength of that tag alone. The tag did not survive inspection:

- 100% of those raw documents also carry a `search_keyword`, so every one was
  found by searching a word, not by visiting an account.
- They sit at a **median of one post per account** (8,034 posts across 4,261
  accounts). A genuine account crawl looks like the tracked brands: 1,693 posts
  from 10 accounts.
- **One** of 3,233 such accounts was a brand we track.

The tag described the scrape run that found the post, not the account that wrote
it, so those 16,887 posts were relabelled `community`. They are real GCC food
posts and remain in the corpus as consumer signal; only the claim about who
wrote them was wrong.

Practical consequences to expect on the trend pages:

- **Brand and influencer counts are small, and many trends show zero.** The
  tracked accounts contribute 4,441 food posts, of which 2,159 cleared the
  belonging gate, spread across 98 trends. A trend with no brand post means no
  tracked brand posted about it — which is the question these columns exist to
  answer.
- **Their post cards have no thumbnail.** These posts came from the account
  crawl, which stored no media, so `media_key` is null and the card renders
  without an image.

Three filters run before any number here is computed:

1. **Food filter** — every post carries `is_food` (stored in
   `food_intel.post_food`, surfaced on the view), set by a
   logistic regression over its embedding, trained on `gpt-4o` labels
   (93.0% held-out accuracy, 92.7% precision). Only `is_food IS TRUE` is ever
   read. Unclassified posts are withheld, not admitted.
2. **Unreadable captions** — empty captions, and the literal strings `nan`,
   `none`, `null`, `undefined` left by a broken upstream export, are ruled out
   before the model sees them.
3. **Belonging gate** — an assigned brand or influencer post joins a trend only
   if its cosine similarity to that trend's centroid reaches the 10th percentile
   of what the trend's own community members score. BERTopic's `transform`
   returns a nearest topic for every post no matter how distant, so without this
   an off-topic post would be counted into a food trend.

### Reading these numbers honestly

- **When a run is sampled** (`--sample N`), every count is a count *within the
  sample*, not the whole corpus. The sample is a deterministic hash of each
  post's identity, so all stages agree on membership, and it is drawn from
  food-only posts.
- **The two corpora end on different dates.** Community scraping stopped on
  2026-06-23; the tracked brand and influencer accounts were crawled through
  2026-07-26. `as_of` — the anchor for every recency window, including
  `recent_posts`, `previous_posts` and `growth_pct` — is therefore taken from
  the **community** corpus, not from the newest post of any source. Anchoring on
  the overall maximum would end the 56-day window a month past the last
  community post and leave it 40% empty of the source that supplies 99% of the
  volume, making every trend read as collapsing. The cost of the correct anchor
  is that tracked posts published after 2026-06-23 (about 400 of them) count in
  `post_count` and engagement but sit outside the recency comparison.
- **The growth ranking is currently measuring the scraper, not the market.**
  Of the 22 trends with `growth_pct` above 100%, 16 hold more than 80% of their
  posts inside a single two-month window, and all ten of the fastest are cake
  and bakery topics. `Custom Buttercream Cupcakes` ran at 2-9 posts a month for
  two years and then recorded 736 in May 2026 and 663 in June — a keyword crawl
  landing, not a market movement. Until collection is even across topics and
  time, read a high `growth_pct` as "recently collected" and check the trend's
  monthly distribution before quoting it.
- **Volume is the solid field.** Growth is noisier: the 56-day windows hold few
  posts for many trends, so `growth_pct` swings hard on a handful of posts.
  Check `previous_posts` before quoting a rate.
- **Sentiment no longer exists.** It was removed from the pipeline, the table,
  the API and the UI; nothing computes or stores it.
