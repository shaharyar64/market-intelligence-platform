# dashboards-backend

Backend microservice for all dashboards

ok now give me api gateway code for all files and for auth I want to use cognito
and admin controls to create read update delete user and give access to each service

first setup venv

`python3 -m venv venv`

then activate venv

`source venv/bin/activate`

then install requirements

`pip install -r requirements.txt`

to run locally

`python -m uvicorn gateway.app.main:app --reload --port 8000`

`python -m uvicorn services.beer_cider_pricing_service.app.main:app --reload --port 8004`

`honcho -f Procfile.dev start gateway food`

`honcho -f Procfile.dev start gateway food trends-real-estate`

`honcho -f Procfile.dev start`

`python -m services.food_intelligence_service.app.enrichment.run --platforms instagram `

Data scraping service:

```bash
python -m uvicorn services.data_scraping_service.app.main:app --reload --port 8006
```

Set `APIFY_KEY` in `.env`. The dashboard can submit Instagram profiles through the
authenticated gateway at `POST /api/v1/data-scraping/instagram/profiles`:

```json
{
  "usernames": ["systemamy", "@colgate_malaysia"],
  "include_about_section": false,
  "country": "MYS",
  "industry": "Oral Care",
  "project": "jll_malaysia",
  "save_to_database": true
}
```

For UI progress, start a background job with
`POST /api/v1/data-scraping/instagram/profiles/jobs`, then poll the returned
`progress_url`. The status response includes `completed`, `total`,
`progress_percent`, `current_username`, and per-username errors.

Instagram post extraction from `posts.ipynb` is available at
`POST /api/v1/data-scraping/instagram/posts`. For progress, use
`POST /api/v1/data-scraping/instagram/posts/jobs` and poll the returned URL.
Post requests accept a date range, `save_to_database`, and
`upload_images_to_s3` (enabled by default).

Twitter profile extraction from `twitter/profile.ipynb` is available at
`POST /api/v1/data-scraping/twitter/profiles`. For per-username UI progress,
use `POST /api/v1/data-scraping/twitter/profiles/jobs` and poll the returned URL.

Twitter post extraction from `twitter/posts.ipynb` is available at
`POST /api/v1/data-scraping/twitter/posts`. For per-username progress, use
`POST /api/v1/data-scraping/twitter/posts/jobs`. `end_date` is exclusive,
matching the notebook's behavior.

Twitter advanced keyword extraction from `twitter/keyword_posts.ipynb` is
available at `POST /api/v1/data-scraping/twitter/keywords`. For progress per
keyword, use `POST /api/v1/data-scraping/twitter/keywords/jobs` and poll the
returned URL.

Keyword searches can optionally enable `filter_by_country`. Built-in text
matching is available for `IND`, `UAE`, `SAU`, `USA`, and `GBR`; other
countries can supply `country_filter_terms`.

TikTok profile extraction using Apify actor `nZqIUKyoBelvbSn1g` is available at
`POST /api/v1/data-scraping/tiktok/profiles`. For per-profile progress, use
`POST /api/v1/data-scraping/tiktok/profiles/jobs` and poll the returned URL.

TikTok post extraction using Apify actor `5K30i8aFccKNF5ICs` is available at
`POST /api/v1/data-scraping/tiktok/posts`. For per-URL progress, use
`POST /api/v1/data-scraping/tiktok/posts/jobs`.
TikTok post requests optionally accept `start_date` and `end_date` together;
both boundaries are inclusive and are applied before returning or saving posts.

LinkedIn company profile extraction using Apify actor `AjfNXEI9qTA2IdaAX` is
available at `POST /api/v1/data-scraping/linkedin/profiles`. For progress, use
`POST /api/v1/data-scraping/linkedin/profiles/jobs`.

LinkedIn company post extraction using Apify actor `WI0tj4Ieb5Kq458gB` is
available at `POST /api/v1/data-scraping/linkedin/posts`; progress jobs use
`POST /api/v1/data-scraping/linkedin/posts/jobs`. Date bounds are inclusive.

Instagram recurring schedules are managed through
`/api/v1/data-scraping/instagram/schedules`. Schedules use five-field cron
expressions and IANA timezones. Apply migration `002_create_scraping_schedules.sql`
before starting the scheduler service.
