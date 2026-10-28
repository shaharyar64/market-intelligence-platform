"""
apply_manual_corrections.py — apply a human-reviewed weekly "Reconciliation
Changes" report back into products_source and plaformsV2.

generate_weekly_report.py's Excel workbook includes a "Reconciliation
Changes" sheet (link, column, before, after) for every value products_source
overwrote that week. A reviewer can add two columns to a copy of that sheet:

  - "Corrected" — the verified-correct brand for the product, filled on any
    row for that link regardless of which field `column` reports on.
  - "sub_type" — the verified-correct sub_type for the product, filled only
    where the reviewer has a specific correction (optional).

This reads that reviewed sheet, derives one correction per link, and writes
it into both products_source (confirmed=true immediately — a human review
outranks the normal 2-week auto-confirm streak) and plaformsV2 (backfilled
across all historical dates for that link, since brand/sub_type/segment are
static product attributes, not time-varying like price).

Usage:
    python apply_manual_corrections.py --file "reviewed_report.xlsx"
    python apply_manual_corrections.py --file "reviewed_report.xlsx" --dry-run
"""

import argparse

import openpyxl

from cleaning import CONFIRM_THRESHOLD, SEGMENT_MAPPING, STRICT_SEGMENTS
from db import Database

SHEET_NAME = "Reconciliation Changes"
BRAND_COLUMNS = {"brand", "cleaned_brand"}


def _norm(value) -> str | None:
    if value is None:
        return None
    s = str(value).strip().lower()
    return s or None


def load_corrections(path: str) -> dict[str, dict]:
    """Returns {link: {"brand_fix": str|None, "sub_type_fix": str|None}},
    including only links with at least one genuine correction."""
    wb = openpyxl.load_workbook(path, data_only=True)
    if SHEET_NAME not in wb.sheetnames:
        raise SystemExit(f"Sheet {SHEET_NAME!r} not found in {path}; found: {wb.sheetnames}")
    ws = wb[SHEET_NAME]
    rows = list(ws.iter_rows(values_only=True))
    header = [str(h).strip().lower() if h else "" for h in rows[0]]

    def col_idx(name: str) -> int:
        return header.index(name)

    idx_link = col_idx("link")
    idx_column = col_idx("column")
    idx_after = col_idx("after")
    idx_corrected = col_idx("corrected")
    idx_subtype = col_idx("sub_type")

    corrections: dict[str, dict] = {}
    warnings = []

    for row in rows[1:]:
        link = row[idx_link]
        if not link:
            continue
        field = _norm(row[idx_column])
        after = _norm(row[idx_after])
        corrected = _norm(row[idx_corrected])
        sub_type = _norm(row[idx_subtype])

        entry = corrections.setdefault(link, {"brand_fix": None, "sub_type_fix": None})

        if field in BRAND_COLUMNS and corrected and corrected != after:
            if entry["brand_fix"] not in (None, corrected):
                warnings.append(f"{link}: conflicting brand corrections {entry['brand_fix']!r} vs {corrected!r}")
            entry["brand_fix"] = corrected

        if sub_type:
            if entry["sub_type_fix"] not in (None, sub_type):
                warnings.append(f"{link}: conflicting sub_type corrections {entry['sub_type_fix']!r} vs {sub_type!r}")
            entry["sub_type_fix"] = sub_type

    for w in warnings:
        print(f"WARNING: {w}")

    return {link: v for link, v in corrections.items() if v["brand_fix"] or v["sub_type_fix"]}


def _segment_for(cleaned_brand: str) -> str:
    segment = SEGMENT_MAPPING.get(cleaned_brand.lower())
    return segment if segment in STRICT_SEGMENTS else "other"


def apply_corrections(corrections: dict[str, dict], db: Database, dry_run: bool) -> None:
    ps_updated = 0
    ps_missing = []
    pv2_rows_updated = 0

    with db.connect(override_db="raw_data") as conn:
        with conn.cursor() as cur:
            for link, fix in corrections.items():
                brand_fix = fix["brand_fix"]
                sub_type_fix = fix["sub_type_fix"]
                segment_fix = _segment_for(brand_fix) if brand_fix else None

                print(link)
                if brand_fix:
                    print(f"  brand/cleaned_brand -> {brand_fix!r}  (segment -> {segment_fix!r})")
                if sub_type_fix:
                    print(f"  sub_type -> {sub_type_fix!r}")

                if dry_run:
                    continue

                ps_clauses = []
                ps_params = {"link": link}
                if brand_fix:
                    ps_clauses += ["brand = %(brand)s", "cleaned_brand = %(brand)s"]
                    ps_params["brand"] = brand_fix
                if sub_type_fix:
                    ps_clauses.append("sub_type = %(sub_type)s")
                    ps_params["sub_type"] = sub_type_fix
                ps_clauses += ["confirmed = true", f"match_streak = GREATEST(match_streak, {CONFIRM_THRESHOLD})"]
                cur.execute(
                    f"UPDATE beer_pricing_analysis.products_source SET {', '.join(ps_clauses)} WHERE link = %(link)s",
                    ps_params,
                )
                if cur.rowcount == 0:
                    ps_missing.append(link)
                else:
                    ps_updated += cur.rowcount

                pv2_clauses = []
                pv2_params = {"link": link}
                if brand_fix:
                    pv2_clauses += ["brand = %(brand)s", "cleaned_brand = %(brand)s", "segment = %(segment)s"]
                    pv2_params["brand"] = brand_fix
                    pv2_params["segment"] = segment_fix
                if sub_type_fix:
                    pv2_clauses.append("sub_type = %(sub_type)s")
                    pv2_params["sub_type"] = sub_type_fix
                cur.execute(
                    f'UPDATE beer_pricing_analysis."plaformsV2" SET {", ".join(pv2_clauses)} WHERE link = %(link)s',
                    pv2_params,
                )
                pv2_rows_updated += cur.rowcount
        if not dry_run:
            conn.commit()

    print()
    if dry_run:
        print(f"Dry run: {len(corrections)} link(s) would be corrected (no writes made)")
    else:
        print(f"products_source: {ps_updated} link(s) updated")
        if ps_missing:
            print(f"products_source: {len(ps_missing)} link(s) NOT found (skipped, needs manual review): {ps_missing}")
        print(f"plaformsV2: {pv2_rows_updated} row(s) updated across all historical dates")


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Apply a human-reviewed reconciliation report to products_source and plaformsV2."
    )
    parser.add_argument("--file", required=True, help="Path to the reviewed .xlsx file.")
    parser.add_argument("--dry-run", action="store_true", help="Print planned changes without writing.")
    args = parser.parse_args()

    corrections = load_corrections(args.file)
    print(f"{len(corrections)} link(s) need correction\n")

    db = Database("raw_data")
    apply_corrections(corrections, db, args.dry_run)


if __name__ == "__main__":
    main()
