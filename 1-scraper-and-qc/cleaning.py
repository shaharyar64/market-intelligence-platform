"""
cleaning.py — clean & reconcile scraped beer pricing data, then push to
beer_pricing_analysis.plaformsV2.

Converted from cleaning_v2.ipynb. Run after run_all_scrapers.py /
extract_from_html_manifests.py have finished for a given date.

Usage:
    python cleaning.py --date 2026-06-18
"""

import argparse
import unicodedata
from urllib.parse import urlparse, urlunparse

import botocore.exceptions
import polars as pl

from db import Database
from s3 import S3Client

S3_BUCKET = "raw-data-prod"

SOURCES = [
    "africanandeastern",
    "africaneastern-abu-dabhi",
    "africaneastern-dubai",
    "africaneastern-rak",
    "mmihomedelivery-dubai",
    "mmihomedelivery-rak",
    "bdutyfree",
    "bmmishops",
    "centaurusint",
    "citydrinks",
    "dubaidutyfree",
    "gbiexpress",
    "gmp",
    "highspiritsuae",
    "jmkcellars",
    "nhsc",
    "premiumcellars",
    "royalspirit",
    "spinneysauh",
    "supercellar",
    "thebottlestore",
    "unisatgt",
    "windmillgt",
]

BAHRAIN_PLATFORMS = ["africanandeastern", "bmmishops", "gbiexpress", "nhsc", "bdutyfree"]

INVALID_CLEANED_BRANDS = [
    "super premium", "premium", "mainstream",
    "strong", "craft / speciality", "cider / flavored", "other",
]

SEGMENT_MAPPING = {
    'almaza': 'mainstream',
    'al maza': 'super premium',
    'asahi': 'super premium',
    'birra moretti': 'super premium',
    'peroni': 'super premium',
    'peroni nastro azzurro': 'super premium',
    'estrella': 'super premium',
    'estrella damm': 'super premium',
    'estrella galicia': 'super premium',
    'dos equis': 'super premium',
    'hitachino': 'super premium',
    'kirin': 'super premium',
    'moritz': 'super premium',
    'alhambra': 'super premium',
    'mahou': 'super premium',
    'modelo': 'super premium',
    'modelo especial': 'super premium',
    'brooklyn': 'craft / speciality',
    'sierra nevada': 'craft / speciality',
    'goose island': 'craft / speciality',
    'pirate life': 'craft / speciality',
    'kaiju': 'craft / speciality',
    'engkanto': 'super premium',
    'quilmes': 'super premium',
    'saigon': 'super premium',
    'chang': 'super premium',
    'mythos': 'super premium',
    'fix': 'super premium',
    'cisk': 'super premium',
    'corona': 'premium',
    'heineken': 'premium',
    'heineken silver': 'premium',
    'stella artois': 'premium',
    'stella': 'premium',
    'san miguel': 'premium',
    'oranjeboom': 'premium',
    'windhoek': 'premium',
    'kronenbourg': 'premium',
    'kronenbourg 1664 lager': 'premium',
    'kronenbourg beer': 'premium',
    'michelob': 'premium',
    'desperados': 'premium',
    'hollandia': 'mainstream',
    'hofbrau': 'craft / speciality',
    'grolsch': 'premium',
    'bavaria': 'premium',
    'schofferhofer': 'premium',
    'maisel': 'craft / speciality',
    'radeberger': 'premium',
    'jever': 'premium',
    'paderborner': 'premium',
    'starnberger': 'other',
    'edelhopfen': 'other',
    'vitalsberg': 'other',
    'amstel': 'mainstream',
    'amstel light': 'mainstream',
    'becks': 'mainstream',
    "beck's": 'mainstream',
    'budweiser': 'mainstream',
    'bud light': 'mainstream',
    'carlsberg': 'mainstream',
    'tiger': 'mainstream',
    'singha': 'mainstream',
    'sol': 'mainstream',
    'tuborg': 'mainstream',
    'holsten': 'mainstream',
    'efes': 'mainstream',
    'efes pilsner': 'mainstream',
    'warsteiner': 'mainstream',
    'warsteiner lager': 'mainstream',
    'krombacher': 'mainstream',
    'krombacher lager': 'mainstream',
    'bitburger': 'mainstream',
    'bitburger beer': 'mainstream',
    'baltika': 'mainstream',
    'baltika lager': 'mainstream',
    'tsingtao': 'mainstream',
    'dab': 'mainstream',
    'carling': 'mainstream',
    'staropramen': 'mainstream',
    'tennents': 'mainstream',
    'lowenbrau': 'mainstream',
    'löwenbräu': 'mainstream',
    'lwenbru': 'mainstream',
    'miller': 'mainstream',
    'okocim': 'mainstream',
    'poretti': 'mainstream',
    'angelo poretti': 'mainstream',
    'just life': 'mainstream',
    'zibert': 'mainstream',
    'budejovicky': 'mainstream',
    'budvar': 'mainstream',
    'castle': 'mainstream',
    'coors': 'mainstream',
    'kilkenny': 'craft / speciality',
    'kaiserdom': 'mainstream',
    'matz': 'mainstream',
    'beirut': 'other',
    'majlis': 'other',
    'kingfisher': 'strong',
    'king fisher': 'strong',
    'king fisher blue premium': 'strong',
    'haywards': 'strong',
    'red horse': 'strong',
    'kalyani': 'strong',
    'godfather': 'strong',
    'lion': 'strong',
    'lion brewery': 'strong',
    'simba': 'strong',
    'royal dutch': 'strong',
    'mannilla': 'strong',
    'mannila': 'strong',
    'manila': 'strong',
    'cobra': 'strong',
    'commando': 'strong',
    'maximus': 'strong',
    'bira': 'strong',
    'himalayan': 'strong',
    'barahsinghe': 'strong',
    '8 horse': 'strong',
    'buffelsfontein': 'strong',
    'loxtonia': 'cider/ flavored',
    'guinness': 'craft / speciality',
    'hoegaarden': 'craft / speciality',
    'hoegarden': 'craft / speciality',
    'blue moon': 'craft / speciality',
    'brewdog': 'craft / speciality',
    'paulaner': 'craft / speciality',
    'murphys': 'craft / speciality',
    'murphys irish stout': 'craft / speciality',
    "murphy's": 'craft / speciality',
    'erdinger': 'craft / speciality',
    'erdinger wheat beer': 'craft / speciality',
    'franziskaner': 'craft / speciality',
    'weihenstephaner': 'craft / speciality',
    'benediktiner': 'craft / speciality',
    'leffe': 'craft / speciality',
    'coopers': 'craft / speciality',
    'abbot': 'craft / speciality',
    'abbot ale': 'craft / speciality',
    'crew republic': 'craft / speciality',
    'duvel': 'craft / speciality',
    'rochehaut': 'craft / speciality',
    "o'hara's": 'craft / speciality',
    'oharas': 'craft / speciality',
    'belhaven': 'craft / speciality',
    'wittekerke': 'craft / speciality',
    "devil's peak": 'craft / speciality',
    'devils peak': 'craft / speciality',
    'petrus': 'craft / speciality',
    'chimay': 'craft / speciality',
    'chouffe': 'craft / speciality',
    'delirium': 'craft / speciality',
    'westmalle': 'craft / speciality',
    'rochefort': 'craft / speciality',
    'orval': 'craft / speciality',
    'affligem': 'craft / speciality',
    'grimbergen': 'craft / speciality',
    'kasteel': 'craft / speciality',
    'kwak': 'craft / speciality',
    'pauwel kwak': 'craft / speciality',
    'lindemans': 'craft / speciality',
    'fruli': 'craft / speciality',
    'la trappe': 'craft / speciality',
    'st. bernardus': 'craft / speciality',
    'st bernardus': 'craft / speciality',
    'gulden draak': 'craft / speciality',
    'piraat': 'craft / speciality',
    'malheur': 'craft / speciality',
    'la guillotine': 'craft / speciality',
    'filou': 'craft / speciality',
    'kristoffel': 'craft / speciality',
    'zundert': 'craft / speciality',
    'tynt meadow': 'craft / speciality',
    'st. feuillien': 'craft / speciality',
    'st feuillien': 'craft / speciality',
    'maredsous': 'craft / speciality',
    'goudale': 'craft / speciality',
    'triple karmeliet': 'craft / speciality',
    'texels': 'craft / speciality',
    'two chefs': 'craft / speciality',
    'moersleutel': 'craft / speciality',
    'jaipur': 'craft / speciality',
    'thornbridge': 'craft / speciality',
    'hobgoblin': 'craft / speciality',
    'old speckled hen': 'craft / speciality',
    'greene king': 'craft / speciality',
    'the white hag': 'craft / speciality',
    'two tribes': 'craft / speciality',
    'de koninck': 'craft / speciality',
    'liefmans': 'craft / speciality',
    'bush': 'craft / speciality',
    'rye river': 'craft / speciality',
    'abbaye st idesbald': 'craft / speciality',
    'henry westons': 'craft / speciality',
    'blackthorn': 'craft / speciality',
    'maeloc': 'cider/ flavored',
    'seven rivers': 'craft / speciality',
    'craft nation': 'craft / speciality',
    'snowy': 'craft / speciality',
    'grins': 'craft / speciality',
    'knig ludwig': 'craft / speciality',
    'könig ludwig': 'craft / speciality',
    'hop house': 'craft / speciality',
    'hunters': 'cider/ flavored',
    "hunter's": 'cider/ flavored',
    'hunter': 'cider/ flavored',
    'hunters gold': 'cider/ flavored',
    'hunters hard lemon': 'cider/ flavored',
    'savanna': 'cider/ flavored',
    'savanna dry angry lemon': 'cider/ flavored',
    'strongbow': 'cider/ flavored',
    'thatchers': 'cider/ flavored',
    'magners': 'cider/ flavored',
    'rekorderlig': 'cider/ flavored',
    'weston cider': 'cider/ flavored',
    'somersby': 'cider/ flavored',
    'crabbies': 'cider/ flavored',
    "crabbie's": 'cider/ flavored',
    'salitos': 'cider/ flavored',
    'kopparberg': 'cider/ flavored',
    'kiss': 'cider/ flavored',
    'heineken 0.0': 'non alc',
    'smirnoff': 'other',
    'bacardi': 'other',
    'cutty sark': 'other',
    'manito mezcal': 'other',
    'manito': 'other',
    'heavensake': 'other',
    'dassai': 'other',
    'sho chiku bai': 'other',
    'x mark vodka': 'other',
    'x mark': 'other',
    'xmark': 'other',
    'x-mark': 'other',
    'x - mark': 'other',
    'buzz vodka orange': 'other',
    'mg spirit mojito': 'other',
    'mg spirit vodka lime': 'other',
    'mg': 'other',
    'oj': 'other',
    'revo energy': 'other',
    'revo': 'other',
    'corelli': 'other',
    'buzz': 'other',
    'purple parrot': 'other',
    'oryx': 'other',
    'oryx sun tap': 'other',
    'greenberg': 'other',
    'malayali': 'other',
    'kamasutra': 'other',
    'side hustle': 'other',
    'codys': 'other',
    'cody': 'other',
    "cody's": 'other',
    'penguin': 'other',
    'mio': 'other',
    'cruise': 'other',
    'red rose': 'other',
    'swahill': 'other',
    'bear': 'other',
    'wild star': 'other',
    'royal spirit': 'other',
    'chumchurum': 'other',
    'ampm': 'other',
    'am:pm': 'other',
    'wignac': 'other',
    'artevelde': 'other',
    'brewgooder': 'other',
    'black devil': 'other',
    'colt': 'other',
    'ryders': 'other',
    'knock out': 'other',
    '66': 'other',
    'na': 'other',
    'ok': 'other',
    'rockberg': 'other',
    'good of san sebastian': 'other',
    'other': 'other',
}

STRICT_SEGMENTS = [
    "super premium", "premium", "mainstream",
    "strong", "craft / speciality", "cider/ flavored", "other",
]

RECONCILE_COLS = ["cleaned_brand", "sub_type", "platform", "brand", "pack_format"]

# Confidence-gated freeze: a link only becomes a trusted products_source
# entry (confirmed = true) once its extracted RECONCILE_COLS values agree
# across this many independent weekly runs.
CONFIRM_THRESHOLD = 2

# If a single `link` value covers this many or more distinct `brand` values
# within one run, it's almost certainly a shared/placeholder URL (e.g. a
# retailer's WhatsApp contact link reused across many products) rather than
# a real per-product URL — freezing/updating products_source for it would
# let one product's data silently overwrite unrelated ones.
SHARED_LINK_BRAND_THRESHOLD = 3


def _normalize_link(link: str | None) -> str | None:
    """Normalize superficial URL variants (scheme/host case, trailing
    slash) so the same physical product page isn't treated as a distinct
    "new" link purely because of how a given scrape happened to format it."""
    if not link:
        return link
    parsed = urlparse(link.strip())
    path = parsed.path.rstrip("/") or "/"
    return urlunparse((parsed.scheme.lower(), parsed.netloc.lower(), path, parsed.params, parsed.query, ""))

PACK_FORMAT_PATTERNS = [
    (r"\bcan(?:s|ned)?\b", "Can"),
    (r"\bkegs?\b|\bdraught\b|\bdraft\b", "Keg"),
    (r"\bbottles?\b|\bglass\b|\bbtl\b", "Glass"),
]


def normalize_pack_format(df: pl.DataFrame) -> pl.DataFrame:
    """Infer pack_format from product_name where it is NA or missing."""
    import re as _re

    def infer(name: str | None) -> str | None:
        if not name:
            return None
        text = name.lower()
        for pattern, fmt in PACK_FORMAT_PATTERNS:
            if _re.search(pattern, text):
                return fmt
        return None

    inferred = pl.Series(
        "pack_format_inferred",
        [infer(n) for n in df["product_name"].to_list()],
    )
    df = df.with_columns(inferred)
    df = df.with_columns(
        pl.when(pl.col("pack_format").is_null() | (pl.col("pack_format") == "NA") | (pl.col("pack_format") == ""))
        .then(pl.col("pack_format_inferred"))
        .otherwise(pl.col("pack_format"))
        .alias("pack_format")
    )
    return df.drop("pack_format_inferred")


def load_raw_data(s3: S3Client, run_date: str) -> list[dict]:
    all_data = []
    skipped = []
    for source in SOURCES:
        try:
            data = s3.read_json(f"s3://{S3_BUCKET}/beer-pricing/{source}/{run_date}.json")
        except botocore.exceptions.ClientError as e:
            if e.response.get("Error", {}).get("Code") in ("NoSuchKey", "404"):
                print(f"Skipping {source} ------- no manifest for {run_date} (scraper likely failed that day)")
                skipped.append(source)
                continue
            raise
        print(f"Got {source} ------- {len(data)}")
        all_data.extend(data)
    print(f"Got final {len(all_data)}")
    if skipped:
        print(f"Skipped {len(skipped)} source(s) with no data for {run_date}: {', '.join(skipped)}")
    return all_data


def _strip_diacritics(s: str | None) -> str | None:
    """Transliterate accented characters (e.g. ö -> o, ä -> a) instead of
    dropping them outright, so e.g. "Löwenbräu" cleans to "lowenbrau" rather
    than the mangled "lwenbru"."""
    if s is None:
        return None
    return unicodedata.normalize("NFKD", s).encode("ascii", "ignore").decode("ascii")


# Brand names where a stoplist word (below) is part of the brand's actual
# identity, not a generic descriptor to strip — e.g. "Bud Light" is a
# distinct brand, not "Budweiser" + a "light" qualifier.
PROTECTED_MULTIWORD_BRANDS = {"bud light"}


def clean_brand(df: pl.DataFrame) -> pl.DataFrame:
    df = df.with_columns(
        pl.col("brand")
        .cast(pl.Utf8)
        .map_elements(_strip_diacritics, return_dtype=pl.Utf8)
        .str.to_lowercase()
        .str.strip_chars()
        .str.replace_all(r"[^a-z0-9\s]", "")
        .str.replace_all(r"\s+", " ")
        .str.strip_chars()
        .alias("_brand_normalized")
    )
    df = df.with_columns(
        pl.when(pl.col("_brand_normalized").is_in(PROTECTED_MULTIWORD_BRANDS))
        .then(pl.col("_brand_normalized"))
        .otherwise(
            pl.col("_brand_normalized")
            .str.replace_all(r"\b(strong|light|ipa|weissbier|pils|imported|beer|cider)\b", "")
            .str.replace_all(r"\s+", " ")
            .str.strip_chars()
        )
        .alias("cleaned_brand")
    ).drop("_brand_normalized")
    return df.with_columns(
        pl.when(pl.col("cleaned_brand").is_in(INVALID_CLEANED_BRANDS))
        .then(None)
        .otherwise(pl.col("cleaned_brand"))
        .alias("cleaned_brand")
    )


def assign_country(df: pl.DataFrame) -> pl.DataFrame:
    return df.with_columns(
        pl.when(pl.col("platform").is_in(BAHRAIN_PLATFORMS))
        .then(pl.lit("Bahrain"))
        .otherwise(pl.lit("UAE"))
        .alias("country")
    )


def assign_segment(df: pl.DataFrame) -> tuple[pl.DataFrame, list[dict]]:
    segment_mapping_lower = {k.lower(): v for k, v in SEGMENT_MAPPING.items()}
    df = df.with_columns(
        pl.col("cleaned_brand").str.to_lowercase().replace(segment_mapping_lower).alias("segment_temp")
    )
    df = df.with_columns(
        pl.when(pl.col("segment_temp").is_in(STRICT_SEGMENTS))
        .then(pl.col("segment_temp"))
        .otherwise(pl.lit("other"))
        .alias("segment")
    )

    # segment_temp only lands outside STRICT_SEGMENTS when cleaned_brand had
    # no entry in SEGMENT_MAPPING at all — surface those brands instead of
    # letting them disappear silently into "other".
    unmapped = (
        df.filter((pl.col("segment") == "other") & pl.col("cleaned_brand").is_not_null())
        .group_by("cleaned_brand")
        .len()
        .sort("len", descending=True)
    )
    unmapped_report = [
        {"cleaned_brand": row["cleaned_brand"], "count": row["len"]}
        for row in unmapped.iter_rows(named=True)
    ]
    if unmapped_report:
        print(f"assign_segment: {len(unmapped_report)} distinct brand(s) not in SEGMENT_MAPPING, defaulted to 'other':")
        for row in unmapped_report:
            print(f"  {row['cleaned_brand']!r} x{row['count']}")

    return df.drop("segment_temp"), unmapped_report


SUB_TYPE_NORMALISE = {
    "blonde": "blond",
    "original lager": "lager",
}


def normalize_sub_type(df: pl.DataFrame) -> pl.DataFrame:
    """Standardise sub_type values: apply alias map, then default null/empty/NA to 'regular'."""
    df = df.with_columns(
        pl.col("sub_type")
        .str.to_lowercase()
        .str.strip_chars()
        .replace(SUB_TYPE_NORMALISE)
        .alias("sub_type")
    )
    return df.with_columns(
        # "na"/"n/a" is what data_extractor.py writes when it can't determine a
        # sub_type — treat it the same as null/empty, not as a distinct value.
        pl.when(pl.col("sub_type").is_null() | pl.col("sub_type").is_in(["", "na", "n/a"]))
        .then(pl.lit("regular"))
        .otherwise(pl.col("sub_type"))
        .alias("sub_type")
    )


def reconcile_with_source_of_truth(df: pl.DataFrame, db: Database) -> tuple[pl.DataFrame, list[dict]]:
    """Where a link has a *confirmed* row in products_source (i.e. its
    extracted values have agreed across CONFIRM_THRESHOLD independent
    weekly runs — see reconcile_pending_links), prefer that table's values
    over this run's freshly (LLM-)extracted ones. Links that are still
    pending pass through with their freshly-extracted values untouched,
    so a single bad first-week extraction can no longer freeze itself in
    permanently. Returns (df, changes) where changes is a per-row,
    per-column log of every value that got overwritten."""
    source_of_truth = db.read_sql(
        f"SELECT link, {', '.join(RECONCILE_COLS)} FROM beer_pricing_analysis.products_source "
        "WHERE confirmed = true",
        override_db="raw_data",
    )
    assert source_of_truth["link"].n_unique() == source_of_truth.height

    rows_before = df.height
    links = df["link"]
    before = df.select(RECONCILE_COLS)

    df = df.join(source_of_truth, on="link", how="left", suffix="_truth")
    assert df.height == rows_before

    matched = (
        df.select([f"{c}_truth" for c in RECONCILE_COLS])
        .select(pl.any_horizontal(pl.all().is_not_null()))
        .to_series()
        .sum()
    )

    for col in RECONCILE_COLS:
        df = df.with_columns(pl.coalesce([pl.col(f"{col}_truth"), pl.col(col)]).alias(col))

    after = df.select(RECONCILE_COLS)
    df = df.drop([f"{col}_truth" for col in RECONCILE_COLS])

    changes = []
    for col in RECONCILE_COLS:
        # null-safe: plain `!=` treats any null-involving comparison as null,
        # which `.sum()` then silently skips, undercounting corrections that
        # backfilled a previously-null value.
        diff_mask = before[col].ne_missing(after[col])
        changed = diff_mask.sum()
        print(f"{col}: {changed} row(s) corrected from source of truth")
        if changed:
            for link, was, now in zip(
                links.filter(diff_mask).to_list(),
                before[col].filter(diff_mask).to_list(),
                after[col].filter(diff_mask).to_list(),
            ):
                changes.append({"link": link, "column": col, "before": was, "after": now})
    print(f"({matched} of {df.height} rows matched a CONFIRMED link in products_source)")

    return df, changes


def _is_invalid_reconcile_value(value) -> bool:
    return value is None or (isinstance(value, str) and value.strip().upper() in ("", "NA", "N/A"))


def _row_has_invalid_value(row: dict) -> bool:
    """True if any RECONCILE_COLS field is missing/NA this week. Agreement
    across weeks is not the same as validity — two consecutive failed
    extractions would otherwise "agree" with each other and get frozen into
    products_source as if NA were a real, trustworthy value."""
    return any(_is_invalid_reconcile_value(row[c]) for c in RECONCILE_COLS)


def _links_already_written_for_date(db: Database, run_date: str) -> set[str]:
    """Links an earlier cleaning.py run already wrote for run_date. Must be
    read before delete_existing_rows_for_date."""
    with db.connect(override_db="raw_data") as conn, conn.cursor() as cur:
        cur.execute(
            'SELECT DISTINCT link FROM beer_pricing_analysis."plaformsV2" WHERE date = %s',
            (run_date,),
        )
        return {r[0] for r in cur.fetchall()}


def reconcile_pending_links(df: pl.DataFrame, db: Database, run_date: str) -> dict:
    """Confidence-gated freeze for products_source.

    For every link in this run (already coalesced with any CONFIRMED source
    of truth by reconcile_with_source_of_truth — pending/new links keep
    their freshly-extracted values, since they weren't matched there):

    - Any RECONCILE_COLS field is missing/NA this week -> skip entirely: not
      inserted, not confirmed, not reset. NA never becomes a "candidate,"
      valid or not — it just leaves whatever pending/absent state existed
      untouched until a real value shows up.
    - Not yet in products_source at all -> insert as pending
      (confirmed=false, match_streak=1) with this week's values as the
      candidate.
    - In products_source, still pending -> if this week's values agree with
      the stored candidate, increment match_streak (and flip to confirmed
      once CONFIRM_THRESHOLD is reached); otherwise the candidate was
      unstable, so reset match_streak=1 and overwrite the candidate with
      this week's values instead of freezing a value that never repeated.
    - In products_source, already confirmed -> nothing to do here; already
      handled by the coalesce upstream.
    - Already written for run_date by an earlier run (a same-day re-run after
      fixing a failed scraper) -> skip, so one week never counts twice
      toward the streak. Only links new to this date are reconciled.
    """
    # ponytail: if a previous run committed products_source but crashed before
    # writing plaformsV2, its links still count twice; track a per-link
    # last-counted date if that ever happens.
    already_counted = _links_already_written_for_date(db, run_date)
    if already_counted:
        print(
            f"products_source: {len(already_counted)} link(s) already counted for {run_date} "
            "by an earlier run — not re-counting them (re-run)"
        )

    link_brand_diversity = df.group_by("link").agg(pl.col("brand").n_unique().alias("distinct_brands"))
    suspicious_links = set(
        link_brand_diversity.filter(pl.col("distinct_brands") >= SHARED_LINK_BRAND_THRESHOLD)["link"].to_list()
    )
    if suspicious_links:
        print(
            f"products_source: {len(suspicious_links)} link(s) look like a shared/placeholder URL "
            f"(>= {SHARED_LINK_BRAND_THRESHOLD} distinct brands sharing one link this run) — "
            "SKIPPING products_source updates for these, needs manual review:"
        )
        for link in sorted(suspicious_links):
            print(f"  {link}")

    existing = db.read_sql(
        f"SELECT link, confirmed, match_streak, {', '.join(RECONCILE_COLS)} "
        "FROM beer_pricing_analysis.products_source",
        override_db="raw_data",
    )
    existing_by_link = {row["link"]: row for row in existing.to_dicts()}

    cols = ["link"] + RECONCILE_COLS
    this_run = df.unique(subset=["link"], keep="first").select(cols).to_dicts()

    new_links, confirmed_links, incremented_links, reset_links, invalid_links = [], [], [], [], []

    with db.connect(override_db="raw_data") as conn:
        with conn.cursor() as cur:
            for row in this_run:
                link = row["link"]
                if link in suspicious_links or link in already_counted:
                    continue

                if _row_has_invalid_value(row):
                    invalid_links.append(row)
                    continue

                existing_row = existing_by_link.get(link)

                if existing_row is None:
                    cur.execute(
                        f"""INSERT INTO beer_pricing_analysis.products_source
                            ({", ".join(cols)}, confirmed, match_streak)
                            VALUES ({", ".join(f"%({c})s" for c in cols)}, false, 1)
                            ON CONFLICT (link) DO NOTHING""",
                        row,
                    )
                    new_links.append(row)
                    continue

                if existing_row["confirmed"]:
                    continue

                agrees = all(existing_row[c] == row[c] for c in RECONCILE_COLS)

                if agrees:
                    new_streak = existing_row["match_streak"] + 1
                    now_confirmed = new_streak >= CONFIRM_THRESHOLD
                    cur.execute(
                        """UPDATE beer_pricing_analysis.products_source
                           SET match_streak = %s, confirmed = %s
                           WHERE link = %s""",
                        (new_streak, now_confirmed, link),
                    )
                    (confirmed_links if now_confirmed else incremented_links).append(row)
                else:
                    set_clause = ", ".join(f"{c} = %({c})s" for c in RECONCILE_COLS)
                    cur.execute(
                        f"""UPDATE beer_pricing_analysis.products_source
                            SET match_streak = 1, {set_clause}
                            WHERE link = %(link)s""",
                        row,
                    )
                    reset_links.append(row)
        conn.commit()

    print(f"\nproducts_source: {len(new_links)} new link(s) added as pending (not yet confirmed):")
    for row in new_links:
        print(f"  {row['link']}")
        print(f"    brand={row['brand']}  sub_type={row['sub_type']}  pack_format={row['pack_format']}")
    if incremented_links:
        print(f"products_source: {len(incremented_links)} pending link(s) agreed again (streak incremented, still not confirmed)")
    if confirmed_links:
        print(f"products_source: {len(confirmed_links)} link(s) newly CONFIRMED this run:")
        for row in confirmed_links:
            print(f"  {row['link']} -> brand={row['brand']}  sub_type={row['sub_type']}  pack_format={row['pack_format']}")
    if reset_links:
        print(f"products_source: {len(reset_links)} pending link(s) disagreed with prior candidate, streak reset:")
        for row in reset_links:
            print(f"  {row['link']}")
    if invalid_links:
        print(
            f"products_source: {len(invalid_links)} link(s) skipped (NA/missing field this run — "
            "never eligible to freeze until a real value is extracted):"
        )
        for row in invalid_links:
            na_fields = [c for c in RECONCILE_COLS if _is_invalid_reconcile_value(row[c])]
            print(f"  {row['link']} -> NA in: {', '.join(na_fields)}")
    if not (new_links or incremented_links or confirmed_links or reset_links or invalid_links):
        print("products_source: no pending/new link activity this run")

    return {
        "new_links": new_links,
        "confirmed_links": confirmed_links,
        "incremented_count": len(incremented_links),
        "reset_links": reset_links,
        "suspicious_links": sorted(suspicious_links),
        "invalid_links": invalid_links,
    }


def delete_existing_rows_for_date(db: Database, run_date: str) -> None:
    """Make the final write idempotent: if cleaning.py --date X is re-run
    (e.g. after fixing a scraper that failed that day), drop that date's
    previously-written rows first instead of silently duplicating them on
    append."""
    with db.connect(override_db="raw_data") as conn, conn.cursor() as cur:
        cur.execute(
            'DELETE FROM beer_pricing_analysis."plaformsV2" WHERE date = %s',
            (run_date,),
        )
        deleted = cur.rowcount
        conn.commit()
    if deleted:
        print(f"Deleted {deleted} existing row(s) for {run_date} before re-writing (idempotent re-run)")


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Clean and reconcile scraped beer pricing data, then push to the DB."
    )
    parser.add_argument(
        "--date", required=True, help="Run date (YYYY-MM-DD), matching the S3 manifest filenames."
    )
    args = parser.parse_args()

    db = Database("raw_data")
    s3 = S3Client()

    all_data = load_raw_data(s3, args.date)
    if not all_data:
        print(f"No data found for any source on {args.date} — nothing to clean or push.")
        raise SystemExit(1)
    df = pl.DataFrame(all_data)
    df = df.with_columns(
        pl.col("link").map_elements(_normalize_link, return_dtype=pl.Utf8).alias("link")
    )

    df = clean_brand(df)
    df = assign_country(df)
    df, other_segment_brands = assign_segment(df)

    df = df.with_columns(pl.lit(args.date).alias("date"))

    df = df.drop(
        ["product_html_s3_key", "product_html_s3_uri", "product_source_s3_key", "product_source_s3_uri"],
        strict=False,
    )

    df = normalize_sub_type(df)
    df = normalize_pack_format(df)
    df, reconciliation_changes = reconcile_with_source_of_truth(df, db)
    link_outcomes = reconcile_pending_links(df, db, args.date)

    rows_per_platform = {
        row["platform"]: row["len"]
        for row in df.group_by("platform").len().iter_rows(named=True)
    }

    delete_existing_rows_for_date(db, args.date)
    df.write_database(
        table_name="beer_pricing_analysis.plaformsV2",
        connection=db.get_uri(override_db="raw_data"),
        if_table_exists="append",
    )
    print(f"Wrote {df.height} rows to beer_pricing_analysis.plaformsV2 for {args.date}")

    changelog = {
        "date": args.date,
        "total_rows": df.height,
        "rows_per_platform": rows_per_platform,
        "reconciliation_changes": reconciliation_changes,
        "new_links": link_outcomes["new_links"],
        "confirmed_links": link_outcomes["confirmed_links"],
        "incremented_count": link_outcomes["incremented_count"],
        "reset_links": link_outcomes["reset_links"],
        "suspicious_links": link_outcomes["suspicious_links"],
        "invalid_links": link_outcomes["invalid_links"],
        "other_segment_brands": other_segment_brands,
    }
    changelog_key = f"beer-pricing/cleanup-reports/{args.date}/changelog.json"
    s3.put_json(S3_BUCKET, changelog_key, changelog)
    print(f"Wrote cleanup changelog to s3://{S3_BUCKET}/{changelog_key}")


if __name__ == "__main__":
    main()
