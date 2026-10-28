"""
report_brand_duplicates.py — surface likely-duplicate brand strings in
beer_pricing_analysis.products_source for periodic human review.

Two distinct cleaned_brand values can refer to the same real-world brand
when data_extractor.py's BRAND_ALIASES doesn't yet have an entry for a
typo or a brand/sub-brand split (e.g. "goose" vs "goose island"). This
script does NOT auto-merge anything — some near-duplicates are
legitimately distinct brands and merging needs a human judgment call. It
just clusters candidates so they can be reviewed and, if confirmed, added
to BRAND_ALIASES in data_extractor.py.

Usage:
    python report_brand_duplicates.py
"""

import difflib

from db import Database


def _load_brand_counts(db: Database) -> dict[str, int]:
    df = db.read_sql(
        """SELECT cleaned_brand, COUNT(*) AS n
           FROM beer_pricing_analysis.products_source
           WHERE cleaned_brand IS NOT NULL
           GROUP BY cleaned_brand""",
        override_db="raw_data",
    )
    return dict(zip(df["cleaned_brand"].to_list(), df["n"].to_list()))


def _containment_pairs(brands: list[str]) -> list[tuple[str, str]]:
    """One brand is a prefix/suffix "root" of another, e.g. "goose" is a
    root of "goose island" — the classic brand/sub-brand split pattern."""
    pairs = []
    for a in brands:
        for b in brands:
            if a == b:
                continue
            if len(a) >= 3 and (b.startswith(a + " ") or b.endswith(" " + a)):
                pairs.append((a, b))
    return pairs


def _similarity_pairs(brands: list[str], threshold: float = 0.82) -> list[tuple[str, str]]:
    """Near-identical spellings (typos), e.g. "hoegaargen" vs "hoegaarden"."""
    pairs = []
    for i, a in enumerate(brands):
        for b in brands[i + 1 :]:
            if abs(len(a) - len(b)) > 3:
                continue
            ratio = difflib.SequenceMatcher(None, a, b).ratio()
            if ratio >= threshold:
                pairs.append((a, b))
    return pairs


def main() -> None:
    db = Database("raw_data")
    counts = _load_brand_counts(db)
    brands = sorted(counts)

    containment = _containment_pairs(brands)
    similarity = [
        pair
        for pair in _similarity_pairs(brands)
        if pair not in containment and pair[::-1] not in containment
    ]

    print(f"products_source: {len(brands)} distinct cleaned_brand value(s)\n")

    if containment:
        print(f"=== {len(containment)} brand/sub-brand containment candidate(s) (e.g. 'goose' vs 'goose island') ===")
        for a, b in sorted(containment):
            print(f"  {a!r} (n={counts[a]})  <->  {b!r} (n={counts[b]})")
        print()

    if similarity:
        print(f"=== {len(similarity)} near-identical spelling candidate(s) (possible typos) ===")
        for a, b in sorted(similarity):
            print(f"  {a!r} (n={counts[a]})  <->  {b!r} (n={counts[b]})")
        print()

    if not containment and not similarity:
        print("No candidate near-duplicates found.")
        return

    print(
        "Review the pairs above. Confirmed duplicates should be added as an\n"
        "entry in BRAND_ALIASES (data_extractor.py) mapping the wrong spelling\n"
        "to the canonical one — do not merge automatically, some pairs here\n"
        "may be legitimately distinct brands."
    )


if __name__ == "__main__":
    main()
