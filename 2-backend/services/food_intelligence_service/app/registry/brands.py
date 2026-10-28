"""Canonical brand registry.

The DB has no field linking a brand's Instagram account to its TikTok account,
so we map them here. One canonical brand -> one account per platform.

Derived from the food_trends_brands accounts you provided. Entries flagged
CONFIRM are my best-guess pairings — verify during testing and edit here; this
is the only place brand identity is defined.
"""

BRANDS: list[dict] = [
    {"key": "almarai",             "name": "Almarai",              "accounts": {"instagram": "almarai",             "tiktok": "almarai"}},
    {"key": "nada",                "name": "Nada",                 "accounts": {"instagram": "nadadairy",           "tiktok": "nadadairy"}},
    {"key": "nadec",               "name": "NADEC",                "accounts": {"instagram": "nadecfoods",          "tiktok": "nadecfood"}},
    {"key": "al_watania_poultry",  "name": "Al Watania Poultry",   "accounts": {"instagram": "al.watania.poultry",  "tiktok": "alwataniapoultry"}},
    # CONFIRM: IG "Al Safi Arabia" <-> TikTok "AL SAFI DANONE"
    {"key": "alsafi",              "name": "Al Safi Danone",       "accounts": {"instagram": "alsafiarabia",        "tiktok": "al.safi.danone"}},
    # CONFIRM: IG sunbulah.group <-> TikTok sunbulahsocial
    {"key": "sunbulah",            "name": "Sunbulah",             "accounts": {"instagram": "sunbulah.group",      "tiktok": "sunbulahsocial"}},
    {"key": "alyoum",              "name": "Alyoum",               "accounts": {"instagram": "alyoum"}},
    {"key": "halwani_bros",        "name": "Halwani Bros",         "accounts": {"instagram": "halwanibrosksa"}},
    {"key": "la_vache_qui_rit",    "name": "La Vache qui Rit",     "accounts": {"instagram": "lavachequiritfr"}},
    {"key": "nestle_mena",         "name": "Nestlé MENA",          "accounts": {"instagram": "nestlemena"}},
    {"key": "puck",                "name": "Puck Arabia",          "accounts": {"instagram": "puckarabia"}},
    {"key": "sadafco",             "name": "Sadafco",              "accounts": {"instagram": "saudia_milk_"}},
    {"key": "americana_foods",     "name": "Americana Foods",      "accounts": {"tiktok": "americanafoods"}},
    # CONFIRM: is this a real KSA food brand or scrape noise? kept separate from Americana Foods.
    {"key": "american_foods_hamburgueria", "name": "American Foods Hamburgueria", "accounts": {"instagram": "americanfoodsbr"}},
]

# (platform, username_lower) -> brand dict
_ACCOUNT_INDEX: dict[tuple[str, str], dict] = {}
for _b in BRANDS:
    for _platform, _username in _b["accounts"].items():
        _ACCOUNT_INDEX[(_platform, _username.lower())] = _b


def account_to_brand(platform: str, username: str | None) -> dict | None:
    if not username:
        return None
    return _ACCOUNT_INDEX.get((platform, username.lower()))


def list_brands() -> list[dict]:
    return BRANDS


# ── tracked influencers ──────────────────────────────────────────────────
# Brands are listed by hand above because one brand spans two platforms and the
# database has nothing joining its Instagram account to its TikTok one. That
# problem does not exist for influencers: they are Instagram-only and each
# account is its own identity, so hard-coding thirty-odd names here would only
# create a second list to keep in step with the tracked one. They are read from
# instagram_profile instead, which is where "who do we track" is already
# decided.
INFLUENCER_PROJECT = "food_trends_influencers"

_influencers: dict[str, dict] | None = None


def _slug(username: str) -> str:
    return "".join(c if c.isalnum() else "_" for c in username.lower()).strip("_")


def _load_influencers() -> dict[str, dict]:
    """username -> identity, read once per process."""
    global _influencers
    if _influencers is None:
        from services.food_intelligence_service.app.trends import store
        try:
            with store.get_conn() as conn, conn.cursor() as cur:
                cur.execute("""SELECT DISTINCT username FROM public.instagram_profile
                               WHERE project = %s AND username IS NOT NULL""",
                            (INFLUENCER_PROJECT,))
                rows = [r[0] for r in cur.fetchall()]
        except Exception:
            # A registry that cannot reach the database must not take enrichment
            # down with it; brands still resolve from the list above.
            return {}
        _influencers = {u.lower(): {"key": _slug(u), "name": u,
                                    "account_type": "influencer"} for u in rows}
    return _influencers


def account_to_identity(platform: str, username: str | None) -> dict | None:
    """The account behind a post: a tracked brand, a tracked influencer, or None.

    Brands win a name collision, since a brand's own account is the stronger
    claim on it.
    """
    if not username:
        return None
    brand = account_to_brand(platform, username)
    if brand:
        return {"key": brand["key"], "name": brand["name"], "account_type": "brand"}
    if platform != "instagram":
        return None
    return _load_influencers().get(username.lower())
