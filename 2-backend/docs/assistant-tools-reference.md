# Assistant Tools — What the Agent Can Reach

The assistant answers only from these eight tools. Tool selection **is** the
router: there is no intent classifier, no keyword matching, no fallback path.
If a question cannot be served by a tool below, the assistant says it has no
data — which is why a missing tool looks exactly like missing data.

Every tool returns the same envelope, so "found nothing" can never be mistaken
for "answered successfully":

```json
{"ok": true|false, "data": [...], "count": 0, "message": "..."}
```

A turn is capped at **6 tool dispatches**. Beyond that, remaining calls receive
a budget-exhausted reply and the model must answer with what it has.

---

## Data the tools can reach

| Table | Reached by | Holds |
|---|---|---|
| `food_intel.trends` | search_trends, get_trend, compare_trends, get_timeline | 98 generated trends, metrics, timelines, example posts |
| `public.community_posts` | search_posts, aggregate_posts | 568,740 scraped posts (**food-only**, see guard below) |
| `food_intel.post_embedding` | search_posts | 1024-dim vectors for semantic search |
| `food_intel.post_analysis` | list_brands, get_brand_profile | Per-post brand enrichment: themes, products, semiotics |

**Nothing else is reachable.** No web access, no other database, no file
search. The model cannot write SQL — it supplies argument values to
hand-written parameterised queries.

---

## The three filters applied before the model sees anything

1. **Food guard.** Every post query passes through `build_post_where()`, which
   begins `p.is_food IS TRUE` unconditionally — no caller can opt out, not even
   one passing no filters. Without it the assistant would quote a bank or
   telecom post back as food evidence.
2. **Latest run only.** `search_trends` reads the most recent `run_id`, so a
   superseded run cannot surface alongside the current one.
3. **Statement timeouts.** 20s on reads, 30s on aggregates. A slow query fails
   as "lookup failed" rather than hanging the conversation.

---

## Trend tools

### `search_trends` — find trends by topic or category
| | |
|---|---|
| Reads | `food_intel.trends`, latest run |
| Arguments | `query`, `quadrant`, `level`, `limit` (all optional) |
| Returns | trend_id, name, quadrant, post_count, unique_authors, sentiment, volume_index, growth_index, summary, metrics |
| Cap | 20 trends |

`query` matches trend **name and summary text**. `quadrant` filters to
`breakthrough` / `slow-burner` / `mainstream` / `watchlist`. `level` selects
`micro` (default, 88 trends) or `umbrella` (10 categories).

**Two recoveries exist here**, both added after live failures:

- **A quadrant name in `query`** returns nothing, because no trend is *named*
  "breakthrough". The tool retries it as a quadrant filter. This failure
  reported "no breaking-out trends" while 14 existed.
- **A self-chosen filter that hides the answer.** The model volunteers a
  `quadrant` it was never asked for; a wrong guess returns nothing for a trend
  that plainly exists. The tool retries without the guessed filter and sets
  `relaxed_filters` so the answer can say the filter was dropped rather than
  quietly ignoring it.

### `get_trend` — one trend in full
Reads `food_intel.trends`. Requires an exact `trend_id`
(`dubai-chocolate-desserts--demo50k`), **never a display name** — the schema
says so explicitly, because the model kept passing names and every call failed.
Returns narrative, metrics, timeline and example posts.

### `compare_trends` — several trends side by side
Takes `trend_ids` (array of exact ids). Ids that do not exist come back in
`not_found` rather than being silently dropped, so a partial comparison is
visibly partial.

### `get_timeline` — weekly series for one trend
Weekly `post_count`, `engagement`, `unique_authors` for a `trend_id`. Same
id rule as above.

---

## Post tools

### `search_posts` — semantic search over posts
| | |
|---|---|
| Reads | `public.community_posts` joined to `post_embedding` |
| Requires | `query` |
| Filters | platforms, sources, date_from, date_to, countries, min_engagement, hashtag |
| Cap | 50 posts |

Matching is by **meaning**, not keywords: the query is embedded and compared by
cosine distance through the HNSW index. It over-fetches 5× before filtering,
because the index filters after retrieval.

`sources` is how "what do consumers think" is answered — `community` is
consumers, `brand` is brand accounts, `influencer` is creators.

### `aggregate_posts` — counts and sums
Groups by `platform`, `source`, `country` or `month`; measures `count`,
`likes`, `engagement` or `views`. Same filter set as `search_posts`. This is
the only tool that does arithmetic over posts, and it does it in SQL — the
model is never asked to add up numbers itself.

---

## Brand tools

### `list_brands` — which brands are covered
Reads `food_intel.post_analysis`. Returns each brand with its analysed-post
count, total engagement and date range. Also the way to check a brand's
spelling before asking for its profile.

### `get_brand_profile` — what one brand communicates
| | |
|---|---|
| Reads | `food_intel.post_analysis` |
| Requires | `brand` (partial names match) |
| Returns | themes with evidence quotes, products, keywords, languages, engagement, top posts |

Themes and products are **counted across posts in SQL**, not summarised by a
model, so the assistant can say "Cattle Farming appears in 12 posts" rather
than offering an impression. A brand with no analysed posts returns a miss that
points at `list_brands`.

These two tools were added after the assistant answered *"I don't have any data
on Almarai's communication themes"* while 225 analysed Almarai posts sat in
`post_analysis`. The data existed; no tool could read it. **That is the failure
mode to watch for: a missing tool is indistinguishable from missing data.**

---

### `create_trend` — build a new trend from a question

| | |
|---|---|
| Reads | `food_intel.post_embedding`, `food_intel.post_food`, `food_intel.trend_posts` |
| Writes | `food_intel.trends` with `origin='chat'`, `created_by=<caller>`, `source_query` |
| Requires | `query` (the subject in food words); optional `name` |
| Returns | trend_id, name, quadrant, post_count, unique_authors, volume/growth index, `already_covered_by` |

The only tool that writes. It retrieves posts for the query and stores a trend
in the same shape the batch pipeline produces, so the Trends Explorer, the
detail view and the date-range recompute render it with no special handling. It
appears in the explorer under the **Chat-generated** filter.

Four properties worth knowing:

- **It can refuse.** Vector search returns neighbours for any question at all,
  so a trend is only created when enough posts clear the distance gate
  (0.52, on the same scale where in-scope questions land at 0.22-0.36). Below
  that the tool returns a miss and the model is instructed to say so rather than
  describe a trend that was never stored.
- **Retrieval is two-pass.** The query's own hits produce a centroid and the
  neighbourhood is searched again around it. Queries are short English, captions
  are mostly long Arabic; one pass finds the topic but under-recalls it.
- **Its indices are comparable.** `volume_index` and `growth_index` are
  percentile ranks *within a run*, and a percentile over a set of one is 50.0 by
  definition. The raw numbers are ranked into the live run's distribution
  instead, and growth is measured against that run's window totals, so "p79"
  means the same thing on a chat trend as on a discovered one.
- **Asking twice updates, never duplicates.** The trend id is an md5 of the
  label and the caller, so a repeated question upserts the same row.

Call `search_trends` first. If an existing trend already covers the topic,
`already_covered_by` reports the overlap and the answer should point at it
rather than accumulate near-duplicates.

---

## What the assistant genuinely cannot answer

| Question | Why |
|---|---|
| Audience personas | No persona data exists. That page still runs on `foodDummy`. |
| Visual/image analysis | `functional_visual` and `semiotic.visual` are stored in `post_analysis` but no tool exposes them. |
| Anything after `as_of` | The data ends at the corpus's latest post date, not today. |
| Non-food posts | Removed by the food guard by design. |
| Anything outside this corpus | No web access. |

The first two are addressable by adding tools. The rest are properties of the
data.

---

## Tool-description quality

Descriptions matter more than they look: they are the only instruction the
model gets about when and how to call a tool. Every failure found in live
testing was a **description** failure, not a code failure:

| Symptom | Cause | Fix |
|---|---|---|
| "No data on Dubai chocolate" | Model volunteered `quadrant`; wrong guess hid the trend | Description states filters hide results; dispatch retries without them |
| Every `compare_trends` call failed | Model passed display names, not ids | Each id field now names the exact field and shows an example |
| "No breaking-out trends" | `query='breakthrough'` matched no name | Description separates topic from quadrant; dispatch retries as a filter |
| Numbers listed without meaning | Prompt had six grounding rules and none about explaining | Added scale definitions and an explain-don't-list rule |

The pattern is consistent: when the model misuses a tool, the schema failed to
say something a new engineer would also have got wrong. Fix the description
first, then add a recovery in dispatch for the case that still slips through.
