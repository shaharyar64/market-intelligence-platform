"""Shared taxonomy and safeguards for the CEER launch analysis notebook."""

from datetime import date, timedelta
from hashlib import sha256

import polars as pl


TAXONOMY_VERSION = "ceer_market_research_v5"
POST_CLASSIFICATION_VERSION = "ceer_market_research_posts_v5"

THEME_TAXONOMY = {
    "Launch & Brand Narrative": [
        "Teaser & Countdown",
        "World Premiere & Reveal",
        "Product Portfolio & Roadmap",
        "Brand Story & Saudi Design DNA",
    ],
    "Saudi Brand & Industrial Impact": [
        "Vision 2030 & National Ambition",
        "Local Manufacturing & Localisation",
        "Partnerships, Supply Chain & Economic Impact",
        "Talent & Jobs",
    ],
    "Exterior Design & Product Form": [
        "Styling, Proportions & Aerodynamics",
        "Lighting & Signature Details",
        "Doors, Wheels & Exterior Features",
        "Colours, Trims & Vehicle Variants",
    ],
    "Cabin & Passenger Experience": [
        "Interior Materials & Craft",
        "Comfort, Space & Ergonomics",
        "Climate, Privacy & Visibility",
        "Personalisation & Lifestyle Experience",
    ],
    "Performance & Driving Dynamics": [
        "Power & Acceleration",
        "Handling, Suspension & Ride",
        "Steering & Driver Control",
    ],
    "Electric Capability & Regional Readiness": [
        "Battery & Range",
        "Charging & Energy Architecture",
        "Heat, Cooling & Regional Suitability",
    ],
    "Digital Technology & Safety": [
        "Digital Cockpit, Connectivity & Voice",
        "App, OTA & Smart Features",
        "Driver Assistance & Autonomous Capability",
        "Active & Passive Safety",
    ],
    "Ownership & Commercial Access": [
        "Availability, Pre-order & Delivery",
        "Price, Value & Finance",
        "First Edition, Packages & Trims",
        "Warranty, Service & Roadside Support",
    ],
    "Brand & Market Perception": [
        "General Brand Reaction",
        "Quality & Reliability",
        "Competitor Comparison",
        "Purchase Intent & Recommendation",
    ],
}

INTERNAL_THEME = "Data Quality (Internal)"
EXCLUDED_SUB_THEMES = frozenset({
    "Emoji-only Reaction",
    "Unrelated or Spam",
    "No Usable Text",
})

SUB_THEME_TO_THEME = {
    sub_theme: theme
    for theme, sub_themes in THEME_TAXONOMY.items()
    for sub_theme in sub_themes
}
SUB_THEME_TO_THEME.update({sub_theme: INTERNAL_THEME for sub_theme in EXCLUDED_SUB_THEMES})
assert sum(map(len, THEME_TAXONOMY.values())) + len(EXCLUDED_SUB_THEMES) == len(SUB_THEME_TO_THEME)
SENTIMENTS = {"positive", "neutral", "negative"}
REPORTING_THEME = "Brand & Market Perception"


def normalize_theme_labels(frame: pl.DataFrame) -> pl.DataFrame:
    """Remove low-signal labels before client-facing theme reporting."""
    excluded = pl.col("sub_theme").is_in(EXCLUDED_SUB_THEMES)
    return frame.with_columns([
        pl.when(excluded).then(pl.lit(None, dtype=pl.Utf8))
        .otherwise(pl.col("theme")).alias("theme"),
        pl.when(excluded).then(pl.lit(None, dtype=pl.Utf8))
        .otherwise(pl.col("sub_theme")).alias("sub_theme"),
    ])


def matched_window(
    launch: date,
    last_complete_day: date,
    earliest_available_day: date,
    days: int | None = None,
):
    """Return equal-length before and after windows, excluding the launch from before."""
    if last_complete_day < launch:
        raise ValueError("The last complete day must be on or after the launch")
    if days is None:
        days = (last_complete_day - launch).days + 1
    if days < 1:
        raise ValueError("The comparison window must contain at least one day")
    after_end = launch + timedelta(days=days - 1)
    if after_end > last_complete_day:
        raise ValueError("Not enough complete post-launch data for the requested comparison")
    before_start = launch - timedelta(days=days)
    if before_start < earliest_available_day:
        raise ValueError("Not enough pre-launch data for an equal-length comparison")
    return before_start, launch - timedelta(days=1), launch, after_end


def percent_change(before: float, after: float) -> float | None:
    """Return percentage lift, or None when the baseline is zero."""
    if before == 0:
        return None
    return round((after / before - 1) * 100, 1)


def classification_version(kind: str) -> str:
    """Return the taxonomy revision used to invalidate stale classification checkpoints."""
    return POST_CLASSIFICATION_VERSION if kind == "post" else TAXONOMY_VERSION


def text_key(kind: str, content: str) -> str:
    """Stable classification key; repeated text is classified once per kind."""
    normalized = " ".join((content or "").split())
    return sha256(f"{classification_version(kind)}\0{kind}\0{normalized}".encode("utf-8")).hexdigest()


def label_rows_by_text(rows: list[dict], text_column: str) -> list[dict]:
    """Build one database update label per exact saved text, including NULL."""
    labels = {}
    for row in rows:
        raw_text = row[text_column]
        label = (row["theme"], row["sub_theme"])
        if not all(label):
            raise ValueError("Every row needs a theme and sub_theme before database update")
        if raw_text in labels and labels[raw_text] != label:
            raise ValueError(f"Conflicting labels for saved {text_column}")
        labels[raw_text] = label
    return [
        {"raw_text": raw_text, "theme": theme, "sub_theme": sub_theme}
        for raw_text, (theme, sub_theme) in labels.items()
    ]


def validate_batch(items: list[dict], expected_ids: set[str]) -> list[dict]:
    """Reject incomplete or out-of-taxonomy model responses before checkpointing."""
    if len(items) != len(expected_ids) or {item.get("item_id") for item in items} != expected_ids:
        raise ValueError("The response omitted or duplicated classification IDs")
    validated = []
    for item in items:
        sub_theme = item.get("sub_theme")
        confidence = item.get("confidence")
        if sub_theme not in SUB_THEME_TO_THEME:
            raise ValueError(f"Invalid sub-theme: {sub_theme}")
        if item.get("sentiment") not in SENTIMENTS:
            raise ValueError(f"Invalid sentiment: {item.get('sentiment')}")
        if isinstance(confidence, bool) or not isinstance(confidence, (int, float)) or not 0 <= confidence <= 1:
            raise ValueError(f"Invalid confidence: {confidence}")
        validated.append({**item, "theme": SUB_THEME_TO_THEME[sub_theme]})
    return validated
