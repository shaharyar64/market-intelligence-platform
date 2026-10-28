"""
Create an Excel review workbook from sub_type_rules.csv.

The workbook mirrors the CSV and adds one extra all_sub_types column. When a
date is provided, all_sub_types is populated from subtype words actually found
in scraped product names/links for each brand.
It intentionally uses only the Python standard library so it can run in this
project without extra Excel dependencies.
"""

from __future__ import annotations

import argparse
import csv
import json
import re
import zipfile
from pathlib import Path
from xml.sax.saxutils import escape

from botocore.exceptions import ClientError

from extract_from_html_manifests import OUTPUT_KEYS, S3_BUCKET
from s3 import S3Client


DEFAULT_INPUT = Path(__file__).resolve().parent / "sub_type_rules.csv"
DEFAULT_OUTPUT = Path(__file__).resolve().parent / "sub_type_rules_review.xlsx"


def normalize_cell(value: str) -> str:
    return re.sub(r"\s+", " ", str(value or "").strip())


def split_sub_types(value: str) -> list[str]:
    pieces: list[str] = []
    for comma_part in str(value or "").split(","):
        for slash_part in comma_part.split("/"):
            cleaned = normalize_cell(slash_part).lower()
            if cleaned and cleaned not in pieces:
                pieces.append(cleaned)
    return pieces


def load_rules(path: Path) -> tuple[list[dict[str, str]], list[str]]:
    with path.open(newline="", encoding="utf-8-sig") as file:
        reader = csv.DictReader(file)
        required = {"cleaned_brand", "sub_types"}
        if not required.issubset(set(reader.fieldnames or [])):
            raise RuntimeError(f"{path} must contain columns: cleaned_brand, sub_types")

        rows = [
            {
                "cleaned_brand": normalize_cell(row.get("cleaned_brand", "")),
                "sub_types": normalize_cell(row.get("sub_types", "")),
            }
            for row in reader
            if normalize_cell(row.get("cleaned_brand", ""))
        ]

    all_sub_types: list[str] = []
    for row in rows:
        for sub_type in split_sub_types(row["sub_types"]):
            if sub_type not in all_sub_types:
                all_sub_types.append(sub_type)

    return rows, sorted(all_sub_types)


def candidate_pattern(candidate: str) -> str:
    escaped = re.escape(candidate).replace(r"\ ", r"[-_\s]+")
    return rf"(?<![a-z0-9]){escaped}(?![a-z0-9])"


def scan_observed_sub_types(date: str, candidates: list[str]) -> dict[str, list[str]]:
    observed: dict[str, list[str]] = {}
    s3 = S3Client()
    candidates = sorted(
        [candidate for candidate in candidates if candidate != "regular"],
        key=len,
        reverse=True,
    )

    for site, output_template in OUTPUT_KEYS.items():
        uri = f"s3://{S3_BUCKET}/{output_template.format(date=date)}"
        try:
            products = s3.read_json(uri)
        except ClientError as error:
            code = error.response.get("Error", {}).get("Code")
            if code in {"NoSuchKey", "404", "NotFound"}:
                print(f"[SKIP] Missing extracted output: {uri}")
                continue
            raise

        if isinstance(products, dict):
            products = products.get("products") or products.get("items") or [products]
        if not isinstance(products, list):
            print(f"[SKIP] Unexpected JSON shape: {uri}")
            continue

        for product in products:
            if not isinstance(product, dict):
                continue

            brand = normalize_cell(product.get("brand", "")).lower()
            if not brand:
                continue

            text = " ".join(str(value).lower() for value in [
                product.get("product_name", ""),
                product.get("link", ""),
            ] if value)
            text = re.sub(r"\s+", " ", text)

            brand_values = observed.setdefault(brand, [])
            for candidate in candidates:
                if candidate not in brand_values and re.search(candidate_pattern(candidate), text):
                    brand_values.append(candidate)

    return {
        brand: sorted(values)
        for brand, values in observed.items()
    }


def column_name(index: int) -> str:
    name = ""
    while index:
        index, remainder = divmod(index - 1, 26)
        name = chr(65 + remainder) + name
    return name


def sheet_xml(rows: list[list[str]], column_widths: list[int] | None = None) -> str:
    sheet_rows = []
    for row_index, row in enumerate(rows, start=1):
        cells = []
        for column_index, value in enumerate(row, start=1):
            ref = f"{column_name(column_index)}{row_index}"
            style_index = 1 if row_index == 1 else 2
            cells.append(
                f'<c r="{ref}" s="{style_index}" t="inlineStr"><is><t>{escape(str(value))}</t></is></c>'
            )
        row_height = ' ht="32" customHeight="1"' if row_index > 1 else ' ht="22" customHeight="1"'
        sheet_rows.append(f'<row r="{row_index}"{row_height}>{"".join(cells)}</row>')

    dimension = f"A1:{column_name(max(len(row) for row in rows))}{len(rows)}" if rows else "A1"
    cols_xml = ""
    if column_widths:
        cols = []
        for index, width in enumerate(column_widths, start=1):
            cols.append(f'<col min="{index}" max="{index}" width="{width}" customWidth="1"/>')
        cols_xml = f'<cols>{"".join(cols)}</cols>'

    return (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main" '
        'xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships">'
        f'<dimension ref="{dimension}"/>'
        '<sheetViews><sheetView workbookViewId="0"/></sheetViews>'
        '<sheetFormatPr defaultRowHeight="15"/>'
        f'{cols_xml}'
        '<sheetData>'
        f'{"".join(sheet_rows)}'
        '</sheetData>'
        '</worksheet>'
    )


def write_xlsx(
    output_path: Path,
    rules_rows: list[dict[str, str]],
    observed_sub_types_by_brand: dict[str, list[str]],
) -> None:
    rules_sheet = [["brand", "sub_types", "all_sub_types"]]
    rules_sheet.extend(
        [
            row["cleaned_brand"],
            row["sub_types"],
            ", ".join(observed_sub_types_by_brand.get(row["cleaned_brand"].lower(), [])),
        ]
        for row in rules_rows
    )

    sheets: list[tuple[str, list[list[str]]]] = [
        ("sub_type_rules", rules_sheet),
    ]

    sheet_overrides = "\n".join(
        f'  <Override PartName="/xl/worksheets/sheet{index}.xml" '
        'ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.worksheet+xml"/>'
        for index, _ in enumerate(sheets, start=1)
    )
    content_types = """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">
  <Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>
  <Default Extension="xml" ContentType="application/xml"/>
  <Override PartName="/xl/workbook.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet.main+xml"/>
{sheet_overrides}
  <Override PartName="/xl/styles.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.styles+xml"/>
</Types>""".format(sheet_overrides=sheet_overrides)

    root_rels = """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">
  <Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="xl/workbook.xml"/>
</Relationships>"""

    workbook_sheets = "\n".join(
        f'    <sheet name="{escape(name)}" sheetId="{index}" r:id="rId{index}"/>'
        for index, (name, _) in enumerate(sheets, start=1)
    )
    workbook = """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<workbook xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main"
  xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships">
  <sheets>
{workbook_sheets}
  </sheets>
</workbook>""".format(workbook_sheets=workbook_sheets)

    worksheet_rels = "\n".join(
        f'  <Relationship Id="rId{index}" '
        'Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/worksheet" '
        f'Target="worksheets/sheet{index}.xml"/>'
        for index, _ in enumerate(sheets, start=1)
    )
    styles_rel_id = f"rId{len(sheets) + 1}"
    workbook_rels = """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">
{worksheet_rels}
  <Relationship Id="{styles_rel_id}" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/styles" Target="styles.xml"/>
</Relationships>""".format(worksheet_rels=worksheet_rels, styles_rel_id=styles_rel_id)

    styles = """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<styleSheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main">
  <fonts count="2">
    <font><sz val="11"/><name val="Calibri"/></font>
    <font><b/><sz val="11"/><name val="Calibri"/></font>
  </fonts>
  <fills count="1"><fill><patternFill patternType="none"/></fill></fills>
  <borders count="1"><border><left/><right/><top/><bottom/><diagonal/></border></borders>
  <cellStyleXfs count="1"><xf numFmtId="0" fontId="0" fillId="0" borderId="0"/></cellStyleXfs>
  <cellXfs count="3">
    <xf numFmtId="0" fontId="0" fillId="0" borderId="0" xfId="0"/>
    <xf numFmtId="0" fontId="1" fillId="0" borderId="0" xfId="0" applyFont="1" applyAlignment="1">
      <alignment vertical="center" wrapText="1"/>
    </xf>
    <xf numFmtId="0" fontId="0" fillId="0" borderId="0" xfId="0" applyAlignment="1">
      <alignment vertical="top" wrapText="1"/>
    </xf>
  </cellXfs>
</styleSheet>"""

    output_path.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(output_path, "w", compression=zipfile.ZIP_DEFLATED) as workbook_zip:
        workbook_zip.writestr("[Content_Types].xml", content_types)
        workbook_zip.writestr("_rels/.rels", root_rels)
        workbook_zip.writestr("xl/workbook.xml", workbook)
        workbook_zip.writestr("xl/_rels/workbook.xml.rels", workbook_rels)
        workbook_zip.writestr("xl/styles.xml", styles)
        for index, (_, rows) in enumerate(sheets, start=1):
            workbook_zip.writestr(
                f"xl/worksheets/sheet{index}.xml",
                sheet_xml(rows, column_widths=[28, 44, 110]),
            )


def main() -> None:
    parser = argparse.ArgumentParser(description="Generate sub_type_rules_review.xlsx from sub_type_rules.csv")
    parser.add_argument("--input", type=Path, default=DEFAULT_INPUT, help="Path to sub_type_rules.csv")
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT, help="Output .xlsx path")
    parser.add_argument("--date", help="Scrape date used to scan extracted S3 outputs for observed subtype words.")
    args = parser.parse_args()

    rows, all_sub_types = load_rules(args.input)
    observed_sub_types_by_brand = scan_observed_sub_types(args.date, all_sub_types) if args.date else {}
    write_xlsx(args.output, rows, observed_sub_types_by_brand)
    print(
        f"Wrote {args.output} with {len(rows)} brands, "
        f"{len(all_sub_types)} candidate sub_types, "
        f"and observed subtype data for {len(observed_sub_types_by_brand)} brands"
    )


if __name__ == "__main__":
    main()
