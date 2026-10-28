# Food Intelligence Service (`food-intelligence`)

Brand Intelligence + Visual Intelligence over Instagram and TikTok food-brand posts.

Unlike the other (read-only SQL) services, this one has **two paths**:

- **Write path (offline, CLI-triggered):** raw Postgres posts -> normalize -> resolve the post image in S3 -> **LangGraph + OpenAI** 7-node analysis graph -> Postgres `food_intel.post_analysis`. Every text finding is grounded with a verbatim caption phrase; every visual finding is grounded with a description of what is actually visible in the image.
- **Read path (request-time):** Postgres `food_intel.*` -> `/api/v1/brands/...` and `/api/v1/visual/...` -> UI. S3 presigned URLs are minted at request time for the gallery.

Postgres is the only store. There is no MongoDB anywhere in this service.

```
Postgres (instagram_/tiktok_ posts+profiles, project=food_trends_brands)
   -> enrichment.pipeline -> S3 image lookup -> LangGraph agent (OpenAI)
   -> Postgres food_intel.post_analysis / brand_profile
   -> services.brand_service + services.visual_service -> /api/v1/* -> dashboard UI
```

## The analysis graph (7 nodes)

All seven nodes fan out from START in a single superstep and merge into one `assemble` node.

Five **text** nodes read ONLY the post caption:

| node | writes |
| --- | --- |
| `description` | `description`, `language` |
| `keywords` | `keywords` |
| `semiotic_text` | `semiotic.text` |
| `themes` | `themes[]` (label, confidence, verbatim caption evidence) |
| `product_focus` | `product_focus[]` (product, confidence, verbatim caption evidence) |

Two **vision** nodes read ONLY a presigned S3 image URL, never the caption:

| node | writes |
| --- | --- |
| `functional_visual` | `functional_visual[]` over product / ingredient / prepared_food / family / individual / in_home / out_of_home, each with `visual_evidence` |
| `semiotic_visual` | `semiotic.visual` scores over premium / healthy / natural / modern / traditional / sophisticated / indulgent |

Node independence is a hard rule: a caption-less post still gets full visual analysis, and an
image-less post still gets full text analysis. Each node writes only its own output key, so a node
that is skipped (no caption, no image) or that fails after 3 attempts simply leaves its field empty
and never blocks the others. Failures are logged, not recorded on the row; re-run a post with
`--force` to try again.

Everything a post produces lands in one unified JSONB `analysis` column on
`food_intel.post_analysis`, which is the single source of truth. Theme and
product facets are aggregated straight out of that JSONB with
`jsonb_array_elements`; there are no derived child tables to keep in sync.

## Endpoints (proxied as `/api/v1/food-intelligence/...` via the gateway)

Brand Intelligence:
- `GET /api/v1/health`
- `GET /api/v1/brands` - brand selector (brands with enriched data)
- `GET /api/v1/brands/{key}/overview` - headline stats, including `visual_territories` (the brand's two strongest semiotic axes)
- `GET /api/v1/brands/{key}/themes?min_posts=&limit=` - communication themes
- `GET /api/v1/brands/{key}/products?min_posts=&limit=` - product focus
- `GET /api/v1/brands/{key}/top-content?limit=&platform=` - top performing content
- `GET /api/v1/brands/{key}/functional-visual` - functional category mix for the brand, with post counts and percentages
- `GET /api/v1/brands/{key}/semiotic` - average semiotic axis scores for the brand

Visual Intelligence (category-wide):
- `GET /api/v1/visual/functional-analysis` - functional category mix across all enriched posts
- `GET /api/v1/visual/semiotic?group_by=industry` - semiotic axis averages grouped by brand industry
- `GET /api/v1/visual/gallery?limit=` - recent posts that have an image, with short-lived presigned S3 URLs

## Database schema

Apply `shared/migrations/002_create_food_intel_schema.sql` then
`shared/migrations/003_drop_food_intel_derived_tables.sql` once before the first enrichment run.
Together they leave the `food_intel` schema holding `post_analysis` and `brand_profile`.

`brand_profile` exists only to materialize the hardcoded `registry/brands.py`
account-to-brand mapping for SQL joins. Follower counts, country, industry and
verification are read live from `public.instagram_profile` / `public.tiktok_profiles`
so they never go stale between scrapes.

## Environment (add to the repo `.env`)
```
# Postgres (source posts AND the food_intel analysis schema) - local dev: set a DSN directly
POSTGRES_DSN=postgresql+psycopg2://user:pass@localhost:5432/yourdb
# (prod: leave POSTGRES_DSN empty and set SECRET_NAME / DB_HOST / DB_NAME like the other services)
SECRET_NAME=
DB_HOST=
DB_PORT=5432
DB_NAME=

# AWS / S3 media (required by the vision nodes and the gallery endpoint)
AWS_REGION=us-east-1
AWS_ACCESS_KEY_ID=...
AWS_SECRET_ACCESS_KEY=...
FOOD_MEDIA_S3_BUCKET=raw-data-bucket
FOOD_MEDIA_S3_PREFIX_TEMPLATE=media/{platform}/

# OpenAI
OPENAI_API_KEY=sk-...
OPENAI_MODEL=gpt-4o-mini        # needs a vision-capable model for the two visual nodes
OPENAI_TEMPERATURE=0

# Cognito (only needed to call the read API through the gateway)
COGNITO_USER_POOL_ID=...
COGNITO_CLIENT_ID=...
```

`FOOD_MEDIA_S3_PREFIX_TEMPLATE` is formatted with `platform`, so the image for a post is looked up
at `s3://$FOOD_MEDIA_S3_BUCKET/{prefix}{post_id}.jpg`. A post with no object there simply skips
both vision nodes and keeps its text analysis.

## Run

Install deps first: `pip install -r requirements.txt`

**1) Enrich (populate `food_intel` in Postgres)** - from the repo root:
```bash
# cheap test run: 20 posts, Instagram only
python -m services.food_intelligence_service.app.enrichment.run --platforms instagram --limit 20

# full run (both platforms, brands)
python -m services.food_intelligence_service.app.enrichment.run

# re-analyze everything (e.g. after changing a prompt)
python -m services.food_intelligence_service.app.enrichment.run --force
```
Idempotent: posts that already have a row are skipped unless `--force`. Each row records `processed_at`, the moment its analysis was written.

**2) Serve the API:**
```bash
python -m uvicorn services.food_intelligence_service.app.main:app --reload --port 8008
# docs: http://localhost:8008/docs
```

## Tests

```bash
pytest services/food_intelligence_service/tests/ -v
```

The default suite needs no database. `tests/db/test_integration_sql.py` executes the service's
hand-written SQL against a real Postgres and is skipped unless `TEST_POSTGRES_DSN` points at a
scratch database it may create and drop objects in:

```bash
TEST_POSTGRES_DSN=postgresql+psycopg2://user:pass@localhost:5432/food_intel_scratch \
  pytest services/food_intelligence_service/tests/db/test_integration_sql.py -v
```

**These tests drop and recreate the entire `food_intel` schema.** Never point `TEST_POSTGRES_DSN`
at a database holding real data, including the one in `POSTGRES_DSN`, which hosts `food_intel`
alongside the source post tables. As a safeguard the module refuses to run unless the target
database name contains `scratch`, `test`, or `tmp`, and raises before executing any statement.
That check is a backstop against a mistyped DSN, not a substitute for verifying the target
yourself.

## Prod activation checklist (do NOT push to `prod` until all done)
The gateway/compose/CI/Procfile are already wired for a `food` service on port 8008. Before the first push to `prod`:
1. Create ECR repo **`dashboards-backend-food`** (CI's "Validate ECR repo exists" step will fail otherwise).
2. Apply `shared/migrations/002_create_food_intel_schema.sql` to the prod database.
3. Add `OPENAI_API_KEY`, `FOOD_MEDIA_S3_BUCKET`, and `FOOD_MEDIA_S3_PREFIX_TEMPLATE` to the `prod-dashboard-env` secret. No Mongo credentials are needed; this service does not use MongoDB.
4. Confirm the task role can `s3:GetObject` and `s3:HeadObject` on `s3://$FOOD_MEDIA_S3_BUCKET/media/*`. Without it the vision nodes are skipped for every post and `/visual/gallery` returns unusable URLs.
5. Insert the `services` DB row (`name='Food Intelligence'`, `route='/food-intelligence'`) and grant it to users.
6. Decide where the enrichment CLI runs in prod (one-off task box). It is not a web process.

## Notes / open items
- **Brand registry** (`app/registry/brands.py`) maps IG and TikTok accounts to canonical brands. Three pairings are flagged `CONFIRM`.
- Enrichment currently targets `food_trends_brands` (Brand Intelligence). Influencers/personas come later.
- `brand_profile.industry` comes from the scraped profile tables; `/visual/semiotic?group_by=industry` only reports brands that have one.
