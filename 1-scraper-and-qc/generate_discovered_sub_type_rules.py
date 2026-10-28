"""
Generate a reviewed subtype rules CSV with discovered subtype candidates.

This script does not change the current extraction logic or the existing
sub_type_rules.csv file. It reads the existing brand -> sub_types rules, scans
stored extracted product outputs, and writes a new CSV:

    brand, sub_types, all_sub_types

`all_sub_types` contains the existing values plus subtype-like descriptors
observed in product names/links for that brand.
"""

from __future__ import annotations

import argparse
import csv
import json
import re
from collections import OrderedDict, defaultdict
from pathlib import Path
from urllib.parse import urlparse

from botocore.exceptions import ClientError

from extract_from_html_manifests import OUTPUT_KEYS, S3_BUCKET
from s3 import S3Client


DEFAULT_INPUT = Path("sub_type_rules.csv")
DEFAULT_OUTPUT = Path("discovered_sub_type_rules.csv")

PACKAGING_WORDS = {
    "0",
    "00",
    "000",
    "1",
    "10",
    "100",
    "12",
    "16",
    "18",
    "2",
    "20",
    "24",
    "25",
    "27",
    "275",
    "3",
    "30",
    "33",
    "330",
    "35",
    "355",
    "4",
    "44",
    "440",
    "47",
    "473",
    "5",
    "50",
    "500",
    "6",
    "8",
    "800",
    "ae",
    "alcohol",
    "and",
    "bbl",
    "beer",
    "beers",
    "bev",
    "beverage",
    "bottle",
    "bottles",
    "btl",
    "btls",
    "can",
    "cans",
    "case",
    "cases",
    "cider",
    "cl",
    "draught",
    "draft",
    "glass",
    "html",
    "keg",
    "kegs",
    "l",
    "litre",
    "litres",
    "ml",
    "non",
    "of",
    "p",
    "pack",
    "packs",
    "pcs",
    "piece",
    "pieces",
    "product",
    "products",
    "sku",
    "tin",
    "tins",
    "x",
}

STYLE_WORDS = {
    "abbey",
    "ale",
    "aluminium",
    "aluminum",
    "amber",
    "barley",
    "belgian",
    "black",
    "blanc",
    "blond",
    "blonde",
    "blue",
    "boom",
    "brune",
    "cherry",
    "classic",
    "dark",
    "double",
    "dry",
    "edition",
    "elephant",
    "extra",
    "fresh",
    "gold",
    "green",
    "heart",
    "hazy",
    "ice",
    "ipa",
    "lager",
    "light",
    "limited",
    "lite",
    "magnum",
    "max",
    "original",
    "pale",
    "pear",
    "pils",
    "pilsener",
    "pilsner",
    "premium",
    "red",
    "rose",
    "silver",
    "special",
    "stout",
    "strong",
    "super",
    "tripel",
    "triple",
    "ultra",
    "weiss",
    "weissbier",
    "wheat",
    "white",
}

STYLE_PHRASES = {
    "black heart",
    "blonde summer",
    "boom strong",
    "double hazy",
    "elvis juice",
    "extra strong",
    "fresh white",
    "limited edition",
    "pale ale",
    "pear cider",
    "punk ipa",
    "shore leave",
    "ultra max",
}

ALIASES = {
    "aluminum": "aluminium",
    "lite": "light",
    "stong": "strong",
}


def clean_text(value: str) -> str:
    value = value.lower()
    value = re.sub(r"https?://\S+", " ", value)
    value = value.replace("&", " and ")
    value = re.sub(r"\b\d+(?:\.\d+)?\s*(?:x|×)\s*\d+(?:\.\d+)?\s*(?:ml|cl|l)\b", " ", value)
    value = re.sub(r"\b\d+(?:\.\d+)?\s*(?:ml|cl|l|litre|litres|%)\b", " ", value)
    value = re.sub(r"\b\d+(?:\.\d+)?\s*pack\b", " ", value)
    value = re.sub(r"[^a-z0-9]+", " ", value)
    return re.sub(r"\s+", " ", value).strip()


def normalize_subtype(value: str) -> str:
    words = [ALIASES.get(word, word) for word in clean_text(value).split()]
    return " ".join(words).strip()


def split_subtypes(value: str) -> list[str]:
    parts = []
    for raw in str(value or "").split(","):
        subtype = normalize_subtype(raw)
        if subtype:
            parts.append(subtype)
    return dedupe(parts)


def dedupe(values: list[str]) -> list[str]:
    seen = set()
    result = []
    for value in values:
        key = normalize_subtype(value)
        if not key or key in seen:
            continue
        seen.add(key)
        result.append(key)
    return result


def load_existing_rules(path: Path) -> OrderedDict[str, list[str]]:
    rules: OrderedDict[str, list[str]] = OrderedDict()
    with path.open("r", encoding="utf-8-sig", newline="") as f:
        reader = csv.DictReader(f)
        for row in reader:
            brand = normalize_subtype(row.get("cleaned_brand") or row.get("brand") or "")
            if not brand:
                continue
            rules[brand] = split_subtypes(row.get("sub_types", ""))
    return rules


def product_strings(product: dict) -> list[str]:
    fields = [
        "product_name",
        "name",
        "title",
        "display_name",
    ]
    return [str(product.get(field, "")) for field in fields if product.get(field)]


def url_text(url: str) -> str:
    parsed = urlparse(url)
    return " ".join(part for part in parsed.path.split("/") if part)


def remove_brand_tokens(tokens: list[str], brand: str) -> list[str]:
    brand_tokens = set(clean_text(brand).split())
    return [token for token in tokens if token not in brand_tokens]


def candidate_tokens(text: str, brand: str) -> list[str]:
    normalized = clean_text(text)
    tokens = []
    for token in normalized.split():
        token = ALIASES.get(token, token)
        if token in PACKAGING_WORDS:
            continue
        if token.isdigit():
            continue
        tokens.append(token)
    return remove_brand_tokens(tokens, brand)


def looks_like_subtype(phrase: str, known_subtypes: set[str]) -> bool:
    if not phrase:
        return False
    if phrase == "regular":
        return False
    if phrase in known_subtypes:
        return True
    if phrase in STYLE_PHRASES:
        return True

    words = phrase.split()
    if len(set(words)) != len(words):
        return False
    if len(words) == 1:
        return words[0] in STYLE_WORDS and words[0] not in {"edition", "limited"}

    return all(word in STYLE_WORDS for word in words)


def discover_from_text(text: str, brand: str, known_subtypes: set[str]) -> list[str]:
    candidates = []
    normalized = clean_text(text)

    for subtype in known_subtypes:
        if subtype != "regular" and re.search(rf"\b{re.escape(subtype)}\b", normalized):
            candidates.append(subtype)

    for phrase in STYLE_PHRASES:
        if re.search(rf"\b{re.escape(phrase)}\b", normalized):
            candidates.append(phrase)

    tokens = candidate_tokens(text, brand)
    for size in (3, 2, 1):
        for index in range(0, max(0, len(tokens) - size + 1)):
            phrase = " ".join(tokens[index : index + size])
            if looks_like_subtype(phrase, known_subtypes):
                candidates.append(phrase)

    return dedupe(candidates)


def read_s3_output(s3: S3Client, site: str, date: str) -> list[dict]:
    key = OUTPUT_KEYS[site].format(date=date)
    uri = f"s3://{S3_BUCKET}/{key}"
    try:
        data = s3.read_json(uri)
    except ClientError as error:
        code = error.response.get("Error", {}).get("Code")
        if code in {"NoSuchKey", "404", "NotFound"}:
            return []
        raise
    if isinstance(data, list):
        return [item for item in data if isinstance(item, dict)]
    return []


def walk_dicts(value) -> list[dict]:
    if isinstance(value, dict):
        dictionaries = [value]
        for nested in value.values():
            dictionaries.extend(walk_dicts(nested))
        return dictionaries
    if isinstance(value, list):
        dictionaries = []
        for nested in value:
            dictionaries.extend(walk_dicts(nested))
        return dictionaries
    return []


def scan_products(products: list[dict], rules: OrderedDict[str, list[str]], observed: dict[str, list[str]]) -> None:
    known_subtypes = {subtype for subtypes in rules.values() for subtype in subtypes}

    for product in products:
        brand = normalize_subtype(product.get("brand", ""))
        if not brand or brand == "na":
            continue

        if product.get("type") not in {None, "", "NA", "beer", "cider", "other"}:
            continue

        rules.setdefault(brand, [])
        text_parts = product_strings(product)
        for text in text_parts:
            observed[brand].extend(discover_from_text(text, brand, known_subtypes))
        observed[brand] = dedupe(observed[brand])


def scan_local_json(path: Path, rules: OrderedDict[str, list[str]], observed: dict[str, list[str]]) -> None:
    with path.open("r", encoding="utf-8") as f:
        data = json.load(f)

    known_subtypes = {subtype for subtypes in rules.values() for subtype in subtypes}
    for item in walk_dicts(data):
        brand = normalize_subtype(
            item.get("brand")
            or item.get("brand_name")
            or item.get("cleaned_brand")
            or ""
        )
        if not brand or brand not in rules:
            continue

        for text in product_strings(item):
            observed[brand].extend(discover_from_text(text, brand, known_subtypes))
        observed[brand] = dedupe(observed[brand])


def write_output(path: Path, rules: OrderedDict[str, list[str]], observed: dict[str, list[str]]) -> None:
    with path.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=["brand", "sub_types", "all_sub_types"])
        writer.writeheader()
        for brand, existing in rules.items():
            all_subtypes = dedupe(existing + observed.get(brand, []))
            writer.writerow(
                {
                    "brand": brand,
                    "sub_types": ", ".join(existing),
                    "all_sub_types": ", ".join(all_subtypes),
                }
            )


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--date", required=True, help="Date to scan, e.g. 2026-05-27")
    parser.add_argument("--input", default=str(DEFAULT_INPUT), help="Existing subtype rules CSV")
    parser.add_argument("--output", default=str(DEFAULT_OUTPUT), help="New output rules CSV")
    parser.add_argument(
        "--extra-json",
        action="append",
        default=[],
        help="Optional local raw JSON file to scan in addition to S3 outputs",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    rules = load_existing_rules(Path(args.input))
    observed: dict[str, list[str]] = defaultdict(list)

    s3 = S3Client()
    total_products = 0
    for site in OUTPUT_KEYS:
        products = read_s3_output(s3, site, args.date)
        total_products += len(products)
        scan_products(products, rules, observed)

    for raw_path in args.extra_json:
        scan_local_json(Path(raw_path), rules, observed)

    output_path = Path(args.output)
    write_output(output_path, rules, observed)
    print(f"Wrote {output_path} from {total_products} extracted products")


if __name__ == "__main__":
    main()
