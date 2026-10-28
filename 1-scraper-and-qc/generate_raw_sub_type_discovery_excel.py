"""
Discover brand subtypes directly from raw product HTML/JSON.

This is a standalone review utility. It does not modify the current extraction
pipeline and does not default missing raw subtypes to regular.

Output workbook columns:
    brand, sub_types, all_sub_types

sub_types:
    Existing configured subtype values from sub_type_rules.csv.

all_sub_types:
    Existing configured subtype values plus subtype-like values discovered
    directly from raw HTML/JSON titles, names, links, and slugs for the same
    brand.
"""

from __future__ import annotations

import argparse
import csv
import html
import json
import re
import zipfile
from collections import Counter, defaultdict
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from urllib.parse import urlparse
from xml.sax.saxutils import escape

from botocore.exceptions import ClientError

from s3 import S3Client


S3_BUCKET = "raw-data-prod"
DEFAULT_RULES = Path("sub_type_rules.csv")
DEFAULT_OUTPUT = Path("raw_sub_type_discovery.xlsx")

MANIFESTS = {
    "africanandeastern": "beer-pricing/africanandeastern/product-html/{date}/manifest.json",
    "africaneastern": "beer-pricing/africaneastern/product-html/{date}/manifest.json",
    "africaneastern_auh": "beer-pricing/africaneastern-abu-dabhi/product-source-json/{date}/manifest.json",
    "africaneastern_dubai": "beer-pricing/africaneastern-dubai/product-source-json/{date}/manifest.json",
    "africaneastern_rak": "beer-pricing/africaneastern-rak/product-source-json/{date}/manifest.json",
    "bdutyfree": "beer-pricing/bdutyfree/product-html/{date}/manifest.json",
    "bmmishops": "beer-pricing/bmmishops/product-source-json/{date}/manifest.json",
    "centaurusint": "beer-pricing/centaurusint/product-html/{date}/manifest.json",
    "citydrinks": "beer-pricing/citydrinks/product-source-json/{date}/manifest.json",
    "dubaidutyfree": "beer-pricing/dubaidutyfree/product-html/{date}/manifest.json",
    "gbiexpress": "beer-pricing/gbiexpress/product-html/{date}/manifest.json",
    "gmp": "beer-pricing/gmp/product-html/{date}/manifest.json",
    "highspiritsuae": "beer-pricing/highspiritsuae/product-html/{date}/manifest.json",
    "jmkcellars": "beer-pricing/jmkcellars/product-html/{date}/manifest.json",
    "mmihomedelivery_dubai": "beer-pricing/mmihomedelivery-dubai/product-html/{date}/manifest.json",
    "mmihomedelivery_rak": "beer-pricing/mmihomedelivery-rak/product-source-json/{date}/manifest.json",
    "nhsc": "beer-pricing/nhsc/product-html/{date}/manifest.json",
    "royalspirit": "beer-pricing/royalspirit/product-source-json/{date}/manifest.json",
    "spinneysauh": "beer-pricing/spinneysauh/product-source-json/{date}/manifest.json",
    "supercellar": "beer-pricing/supercellar/product-html/{date}/manifest.json",
    "thebottlestore": "beer-pricing/thebottlestore/product-html/{date}/manifest.json",
    "unisatgt": "beer-pricing/unisatgt/product-html/{date}/manifest.json",
    "windmillgt": "beer-pricing/windmillgt/product-source-json/{date}/manifest.json",
}

OUTPUT_KEYS = {
    "africanandeastern": "beer-pricing/africanandeastern/{date}.json",
    "africaneastern": "beer-pricing/africaneastern/{date}.json",
    "africaneastern_auh": "beer-pricing/africaneastern-abu-dabhi/{date}.json",
    "africaneastern_dubai": "beer-pricing/africaneastern-dubai/{date}.json",
    "africaneastern_rak": "beer-pricing/africaneastern-rak/{date}.json",
    "bdutyfree": "beer-pricing/bdutyfree/{date}.json",
    "bmmishops": "beer-pricing/bmmishops/{date}.json",
    "centaurusint": "beer-pricing/centaurusint/{date}.json",
    "citydrinks": "beer-pricing/citydrinks/{date}.json",
    "dubaidutyfree": "beer-pricing/dubaidutyfree/{date}.json",
    "gbiexpress": "beer-pricing/gbiexpress/{date}.json",
    "gmp": "beer-pricing/gmp/{date}.json",
    "highspiritsuae": "beer-pricing/highspiritsuae/{date}.json",
    "jmkcellars": "beer-pricing/jmkcellars/{date}.json",
    "mmihomedelivery_dubai": "beer-pricing/mmihomedelivery-dubai/{date}.json",
    "mmihomedelivery_rak": "beer-pricing/mmihomedelivery-rak/{date}.json",
    "nhsc": "beer-pricing/nhsc/{date}.json",
    "royalspirit": "beer-pricing/royalspirit/{date}.json",
    "spinneysauh": "beer-pricing/spinneysauh/{date}.json",
    "supercellar": "beer-pricing/supercellar/{date}.json",
    "thebottlestore": "beer-pricing/thebottlestore/{date}.json",
    "unisatgt": "beer-pricing/unisatgt/{date}.json",
    "windmillgt": "beer-pricing/windmillgt/{date}.json",
}

BRAND_ALIASES = {
    "becks": "beck's",
    "beck": "beck's",
    "brew dog": "brewdog",
    "brewdog": "brewdog",
    "bud": "budweiser",
    "bud light": "budweiser",
    "bud zero": "budweiser",
    "budvar": "budweiser",
    "king fisher": "kingfisher",
    "king fisher blue": "kingfisher",
    "kingfisher blue": "kingfisher",
    "lowenbrau": "löwenbräu",
    "peroni nastro azzurro": "peroni",
    "peroni nastro azzuro": "peroni",
    "redhorse": "red horse",
    "san mig": "san miguel",
    "san mig light": "san miguel",
    "stella": "stella artois",
    "tag premium": "tag",
    "mannilla": "manila",
    "manilla": "manila",
}

EXCLUDED_BRAND_PATTERNS = {
    "2xl vodka",
    "bacardi",
    "bacardi breezer",
    "breezer",
    "buzz",
    "cooler",
    "grins",
    "juice",
    "smirnoff",
    "smirnoff vodka",
    "vodka",
}

KNOWN_BRANDS = {
    "8 horse", "1664", "almaza", "amstel", "asahi", "bacardi breezer",
    "barahsinghe", "beck's", "birra moretti", "bitburger", "blue moon",
    "brew dog", "brewdog", "brooklyn", "bud light", "budweiser", "carlsberg", "chang",
    "chouffe", "corona", "dab", "desperados", "duvel", "efes", "erdinger",
    "estrella", "faxe", "foster's", "goose island", "grins", "guinness",
    "heineken", "hoegaarden", "holsten", "kamasutra", "kingfisher", "kirin",
    "krombacher", "kronenbourg", "leffe", "löwenbräu", "magners",
    "mecklenburger", "michelob", "miller", "old speckled hen", "peroni",
    "petrus", "red horse", "royal dutch", "salitos", "san miguel", "singha",
    "sol", "somersby", "stella artois", "tag", "tiger", "tsingtao",
    "twisted tea", "warsteiner",
}

TYPE_WORDS = {
    "beer", "beers", "cider", "ciders", "lager", "pilsner", "pilsener",
    "pils", "ale", "stout", "wheat", "weissbier", "ipa",
}

PACKAGING_WORDS = {
    "0", "00", "000", "1", "2", "3", "4", "5", "6", "7", "8", "10",
    "12", "16", "18", "20", "21", "24", "25", "27", "275", "30", "33",
    "330", "35", "355", "44", "440", "47", "473", "50", "500", "800",
    "ae", "aed", "alcohol", "and", "bbl", "bottle", "bottles", "btl",
    "btls", "can", "cans", "case", "cases", "cl", "draught", "draft",
    "glass", "html", "keg", "kegs", "l", "litre", "litres", "ml", "non",
    "of", "p", "pack", "packs", "pcs", "piece", "pieces", "product", "sku",
    "tin", "tins", "x",
}

PACKAGING_PHRASES = {
    "beer bottle",
    "beer can",
    "bottle",
    "bottles",
    "can",
    "cans",
    "glass bottle",
    "long neck",
    "long neck bottle",
}

NOISE_WORDS = {
    "a", "about", "after", "all", "an", "are", "as", "at", "best", "buy",
    "by", "category", "choose", "contains", "delivery", "description", "for",
    "free", "from", "home", "in", "item", "items", "made", "more", "new",
    "online", "option", "original", "out", "page", "price", "product",
    "products", "promotion", "save", "shop", "size", "sale", "the", "this",
    "to", "uae", "with", "your",
}

EXCLUDED_TEXT_PATTERNS = [
    re.compile(r"\b0(?:\.0)?\s*%\b"),
    re.compile(r"\bnon[-\s]*alcohol(?:ic)?\b"),
    re.compile(r"\bzero\s+alcohol\b"),
    re.compile(r"\balcohol\s+free\b"),
    re.compile(r"\bvodka\b"),
    re.compile(r"\bbreezer\b"),
    re.compile(r"\bjuice\b"),
]

STYLE_WORDS = {
    "abbey", "ale", "aluminium", "aluminum", "amber", "apple", "barley",
    "belgian", "black", "blanc", "blond", "blonde", "blue", "boom", "brune",
    "cherry", "classic", "dark", "double", "dry", "edition", "extra",
    "fresh", "fruit", "gold", "golden", "green", "heart", "hazy", "ice",
    "ipa", "irish", "lager", "lemon", "light", "limited", "lite", "malt",
    "mango", "max", "original", "pale", "pear", "pils", "pilsener",
    "pilsner", "pineapple", "premium", "red", "rose", "ruby", "silver",
    "special", "stout", "strong", "super", "tripel", "triple", "ultra",
    "watermelon", "weiss", "weissbier", "wheat", "white",
}

STYLE_PHRASES = {
    "black heart", "blue premium", "double hazy", "extra strong",
    "fresh white", "irish cider", "limited edition", "pale ale", "pear cider",
    "premium blue", "punk ipa", "ultra max",
}

SUBTYPE_ALIASES = {
    "aluminum": "aluminium",
    "lite": "light",
    "pilsener": "pilsner",
    "triple": "tripel",
}


def split_subtypes(value: str, keep_regular: bool = True) -> list[str]:
    parts = []
    for comma_part in str(value or "").split(","):
        for slash_part in comma_part.split("/"):
            subtype = normalize_phrase(slash_part)
            if subtype and (keep_regular or subtype != "regular"):
                parts.append(subtype)
    return dedupe(parts, keep_regular=keep_regular)


def load_existing_rules(path: Path) -> dict[str, list[str]]:
    if not path.exists():
        raise RuntimeError(f"Missing subtype rules CSV: {path}")

    rules: dict[str, list[str]] = {}
    with path.open("r", encoding="utf-8-sig", newline="") as file:
        reader = csv.DictReader(file)
        required = {"cleaned_brand", "sub_types"}
        if not required.issubset(set(reader.fieldnames or [])):
            raise RuntimeError(f"{path} must contain columns: cleaned_brand, sub_types")

        for row in reader:
            brand = normalize_phrase(row.get("cleaned_brand", ""))
            if not brand or is_excluded_brand(brand):
                continue
            rules[brand] = split_subtypes(row.get("sub_types", ""), keep_regular=True)

    return rules


def s3_uri(key: str) -> str:
    return f"s3://{S3_BUCKET}/{key}"


def is_missing_s3_key(error: Exception) -> bool:
    if not isinstance(error, ClientError):
        return False
    return error.response.get("Error", {}).get("Code") in {"NoSuchKey", "404", "NotFound"}


def clean_text(value: str) -> str:
    value = html.unescape(str(value or "")).lower()
    value = re.sub(r"<script\b.*?</script>", " ", value, flags=re.IGNORECASE | re.DOTALL)
    value = re.sub(r"<style\b.*?</style>", " ", value, flags=re.IGNORECASE | re.DOTALL)
    value = re.sub(r"<[^>]+>", " ", value)
    value = value.replace("&", " and ")
    value = re.sub(r"https?://\S+", " ", value)
    value = re.sub(r"\b\d+(?:\.\d+)?\s*(?:x|×)\s*\d+(?:\.\d+)?\s*(?:ml|cl|l)\b", " ", value)
    value = re.sub(r"\b\d+(?:\.\d+)?\s*(?:ml|cl|l|litre|litres|%)\b", " ", value)
    value = re.sub(r"\b\d+(?:\.\d+)?\s*pack\b", " ", value)
    value = re.sub(r"[^a-z0-9']+", " ", value)
    return re.sub(r"\s+", " ", value).strip()


def normalize_percent_strength_phrase(value: str) -> str:
    raw = html.unescape(str(value or "")).lower()
    match = re.search(
        r"\b(\d{1,2}(?:\.\d+)?)\s*%\s*(?:abv|alc\.?\s*vol\.?|alcohol)?\s*(extra\s+strong|super\s+strong|strong)\b",
        raw,
        flags=re.IGNORECASE,
    )
    if not match:
        match = re.search(
            r"\b(extra\s+strong|super\s+strong|strong)\s*(?:beer|lager)?\s*(\d{1,2}(?:\.\d+)?)\s*%",
            raw,
            flags=re.IGNORECASE,
        )
        if match:
            percentage = match.group(2).rstrip("0").rstrip(".")
            strength = " ".join(match.group(1).split())
            return f"{percentage}% {strength}"
        return ""

    percentage = match.group(1).rstrip("0").rstrip(".")
    strength = " ".join(match.group(2).split())
    return f"{percentage}% {strength}"


def normalize_phrase(value: str) -> str:
    percent_strength = normalize_percent_strength_phrase(value)
    if percent_strength and clean_text(value).replace(" ", "") in {
        clean_text(percent_strength).replace(" ", ""),
        clean_text(percent_strength.replace("%", " percent ")).replace(" ", ""),
    }:
        return percent_strength
    words = [SUBTYPE_ALIASES.get(word, word) for word in clean_text(value).split()]
    return " ".join(words).strip()


def contains_phrase(text: str, phrase: str) -> bool:
    text = normalize_phrase(text)
    phrase = normalize_phrase(phrase)
    return bool(phrase and re.search(rf"(?<![a-z0-9]){re.escape(phrase)}(?![a-z0-9])", text))


def is_excluded_brand(brand: str) -> bool:
    brand = normalize_phrase(brand)
    return any(contains_phrase(brand, excluded) for excluded in EXCLUDED_BRAND_PATTERNS)


def is_out_of_scope_text(text: str) -> bool:
    normalized = normalize_phrase(text)
    return any(pattern.search(normalized) for pattern in EXCLUDED_TEXT_PATTERNS)


def is_bad_subtype(subtype: str, brand: str = "") -> bool:
    subtype = normalize_phrase(subtype)
    brand = normalize_phrase(brand)

    if not subtype:
        return True
    if subtype in PACKAGING_WORDS or subtype in PACKAGING_PHRASES:
        return True
    if subtype in TYPE_WORDS:
        return True
    if is_out_of_scope_text(subtype):
        return True
    if brand and subtype in {f"{brand} beer", f"{brand} cider", f"{brand} lager"}:
        return True
    if any(subtype in {f"{known_brand} beer", f"{known_brand} cider", f"{known_brand} lager"} for known_brand in KNOWN_BRANDS):
        return True
    if brand and subtype.startswith(f"{brand} "):
        tail = subtype[len(brand) + 1 :]
        if tail in TYPE_WORDS or tail in PACKAGING_PHRASES:
            return True
    if subtype.endswith(" beer") or subtype.endswith(" cider"):
        without_type = re.sub(r"\s+(?:beer|cider)$", "", subtype).strip()
        if not without_type or without_type == brand:
            return True

    return False


def dedupe(values: list[str], keep_regular: bool = False) -> list[str]:
    seen = set()
    result = []
    for value in values:
        normalized = normalize_phrase(value)
        if not normalized or normalized in seen:
            continue
        if normalized == "regular" and not keep_regular:
            continue
        seen.add(normalized)
        result.append(normalized)
    return result


def filter_subtypes(values: list[str], brand: str = "", keep_regular: bool = False) -> list[str]:
    cleaned = []
    for value in values:
        normalized = normalize_phrase(value)
        if normalized.endswith(" beer") or normalized.endswith(" cider"):
            without_type = re.sub(r"\s+(?:beer|cider)$", "", normalized).strip()
            if without_type and without_type != normalize_phrase(brand):
                normalized = without_type
        if normalized and not is_bad_subtype(normalized, brand):
            cleaned.append(normalized)
    cleaned = dedupe(cleaned, keep_regular=keep_regular)

    final = []
    for value in cleaned:
        if value == "regular":
            final.append(value)
            continue
        value_words = set(value.split())
        is_component_of_longer_phrase = any(
            value != other
            and value_words
            and value_words < set(other.split())
            and all(word in STYLE_WORDS for word in value_words)
            for other in cleaned
        )
        if not is_component_of_longer_phrase:
            final.append(value)

    return dedupe(final, keep_regular=keep_regular)


def get_nested_values(value, keys: set[str]) -> list[str]:
    found = []
    if isinstance(value, dict):
        for key, nested in value.items():
            key_l = str(key).lower()
            if key_l in keys and nested not in (None, ""):
                found.append(str(nested))
            found.extend(get_nested_values(nested, keys))
    elif isinstance(value, list):
        for item in value:
            found.extend(get_nested_values(item, keys))
    return found


def extract_json_texts(raw: str) -> list[str]:
    try:
        data = json.loads(raw)
    except json.JSONDecodeError:
        return []

    return get_nested_values(
        data,
        {
            "name", "title", "product_name", "productname", "display_name",
            "slug", "url", "link", "short_description",
        },
    )


def extract_html_texts(raw: str) -> list[str]:
    texts = []
    patterns = [
        r"<h1[^>]*>(.*?)</h1>",
        r"<title[^>]*>(.*?)</title>",
        r'<meta[^>]+property=["\']og:title["\'][^>]+content=["\']([^"\']+)["\']',
        r'<meta[^>]+name=["\']title["\'][^>]+content=["\']([^"\']+)["\']',
        r'"name"\s*:\s*"([^"]+)"',
        r'"productName"\s*:\s*"([^"]+)"',
    ]
    for pattern in patterns:
        texts.extend(re.findall(pattern, raw, flags=re.IGNORECASE | re.DOTALL))
    return [clean_text(text) for text in texts if clean_text(text)]


def url_words(url: str) -> str:
    parsed = urlparse(str(url or ""))
    path = " ".join(part for part in parsed.path.split("/") if part)
    return re.sub(r"\.[a-z0-9]+$", " ", path)


def infer_brand(text: str, fallback: str = "", allowed_brands: set[str] | None = None) -> str:
    normalized = normalize_phrase(" ".join([fallback, text]))
    brand_candidates = set(allowed_brands or [])

    for alias, brand in sorted(BRAND_ALIASES.items(), key=lambda item: len(item[0]), reverse=True):
        if brand in brand_candidates and re.search(rf"(?<![a-z0-9]){re.escape(alias)}(?![a-z0-9])", normalized):
            return brand

    for brand in sorted(brand_candidates, key=len, reverse=True):
        if re.search(rf"(?<![a-z0-9]){re.escape(brand)}(?![a-z0-9])", normalized):
            return brand

    return ""


def remove_brand_tokens(tokens: list[str], brand: str) -> list[str]:
    brand_tokens = set(normalize_phrase(brand).split())
    return [token for token in tokens if token not in brand_tokens]


def subtype_tokens(text: str, brand: str) -> list[str]:
    tokens = []
    for token in normalize_phrase(text).split():
        if token in PACKAGING_WORDS or token in TYPE_WORDS or token in NOISE_WORDS:
            continue
        if token.isdigit():
            continue
        tokens.append(token)
    return remove_brand_tokens(tokens, brand)


def looks_like_subtype(phrase: str) -> bool:
    if not phrase or phrase == "regular":
        return False
    words = phrase.split()
    if len(set(words)) != len(words):
        return False
    if len(words) == 1:
        return words[0] in STYLE_WORDS and words[0] not in {"edition", "limited"}
    return all(word in STYLE_WORDS for word in words)


def discover_strength_percent_subtypes(text: str) -> list[str]:
    value = html.unescape(str(text or "")).lower()
    candidates = []

    for match in re.finditer(
        r"\b(\d{1,2}(?:\.\d+)?)\s*%\s*(?:abv|alc\.?\s*vol\.?|alcohol)?\s*(extra\s+strong|super\s+strong|strong)\b",
        value,
        flags=re.IGNORECASE,
    ):
        percentage = match.group(1).rstrip("0").rstrip(".")
        strength = normalize_phrase(match.group(2))
        candidates.append(f"{percentage}% {strength}")

    for match in re.finditer(
        r"\b(extra\s+strong|super\s+strong|strong)\s*(?:beer|lager)?\s*(\d{1,2}(?:\.\d+)?)\s*%",
        value,
        flags=re.IGNORECASE,
    ):
        strength = normalize_phrase(match.group(1))
        percentage = match.group(2).rstrip("0").rstrip(".")
        candidates.append(f"{percentage}% {strength}")

    return dedupe(candidates)


def discover_subtypes(text: str, brand: str) -> list[str]:
    if is_out_of_scope_text(text):
        return []

    normalized = normalize_phrase(text)
    candidates = discover_strength_percent_subtypes(text)

    for phrase in sorted(STYLE_PHRASES, key=len, reverse=True):
        if re.search(rf"(?<![a-z0-9]){re.escape(phrase)}(?![a-z0-9])", normalized):
            candidates.append(phrase)

    tokens = subtype_tokens(text, brand)
    for size in (3, 2, 1):
        for index in range(0, max(0, len(tokens) - size + 1)):
            phrase = " ".join(tokens[index : index + size])
            if looks_like_subtype(phrase):
                candidates.append(phrase)

    return filter_subtypes(candidates, brand)


def parse_json_object(text: str) -> dict:
    text = str(text or "").strip()
    try:
        data = json.loads(text)
        return data if isinstance(data, dict) else {}
    except json.JSONDecodeError:
        pass

    match = re.search(r"\{.*\}", text, flags=re.DOTALL)
    if not match:
        return {}
    try:
        data = json.loads(match.group(0))
    except json.JSONDecodeError:
        return {}
    return data if isinstance(data, dict) else {}


def llm_discover_subtypes(texts: list[str], brand: str, model: str) -> list[str]:
    from dotenv import load_dotenv
    from langchain_core.messages import HumanMessage, SystemMessage
    from langchain_openai import ChatOpenAI

    load_dotenv()
    compact_lines = []
    for text in texts:
        compact = re.sub(r"\s+", " ", str(text)).strip()
        if compact:
            compact_lines.append(f"- {compact[:500]}")
    compact_text = "\n".join(compact_lines)[:6000]
    if not compact_text:
        return []

    llm = ChatOpenAI(model=model, temperature=0)
    response = llm.invoke(
        [
            SystemMessage(
                content=(
                    "You extract beer/cider subtype candidates for data-quality review. "
                    "Use only the provided raw product text. Do not invent values. "
                    "Do not return brand, package format, quantity, units, prices, or the word regular. "
                    "Return JSON only: {\"sub_types\": [\"...\"]}. "
                    "Valid examples include blue, premium blue, light, ultra max, extra strong, "
                    "8% strong, 12% strong, black heart, punk ipa, pear cider."
                )
            ),
            HumanMessage(content=f"Brand: {brand}\nRaw text:\n{compact_text}"),
        ]
    )
    payload = parse_json_object(getattr(response, "content", response))
    values = payload.get("sub_types", [])
    if not isinstance(values, list):
        return []
    return filter_subtypes([str(value) for value in values], brand)


def read_s3_text(s3: S3Client, uri: str) -> str:
    parsed = urlparse(uri)
    response = s3.s3.get_object(Bucket=parsed.netloc, Key=parsed.path.lstrip("/"))
    return response["Body"].read().decode("utf-8", errors="replace")


def load_manifest(s3: S3Client, site: str, date: str) -> list[dict]:
    uri = s3_uri(MANIFESTS[site].format(date=date))
    try:
        data = s3.read_json(uri)
    except Exception as error:
        if is_missing_s3_key(error):
            print(f"[SKIP] Missing manifest: {uri}")
            return []
        raise

    if isinstance(data, list):
        return [item for item in data if isinstance(item, dict)]
    if isinstance(data, dict):
        items = data.get("items") or data.get("products") or data.get("manifest") or []
        return [item for item in items if isinstance(item, dict)]
    return []


def scan_raw_entry(
    s3: S3Client,
    entry: dict,
    allowed_brands: set[str] | None = None,
    use_llm: bool = False,
    llm_model: str = "gpt-5.4-mini",
) -> tuple[str, list[str]]:
    link = str(entry.get("link") or entry.get("url") or "")
    uri = (
        entry.get("product_html_s3_uri")
        or entry.get("product_source_s3_uri")
        or entry.get("source_s3_uri")
        or entry.get("s3_uri")
    )
    raw = ""
    texts = [link, url_words(link)]

    for field in ("product_name", "name", "title", "slug"):
        if entry.get(field):
            texts.append(str(entry[field]))

    if uri:
        raw = read_s3_text(s3, str(uri))
        stripped = raw.lstrip()
        if stripped.startswith("{") or stripped.startswith("["):
            texts.extend(extract_json_texts(raw))
        else:
            texts.extend(extract_html_texts(raw))

    joined = " ".join(texts)
    if is_out_of_scope_text(joined):
        return "", []

    brand = infer_brand(joined, fallback=link, allowed_brands=allowed_brands)
    if not brand or is_excluded_brand(brand):
        return "", []

    subtypes = []
    for text in texts:
        subtypes.extend(discover_subtypes(text, brand))
    if use_llm:
        subtypes.extend(llm_discover_subtypes(texts, brand, llm_model))
    return brand, filter_subtypes(subtypes, brand)


def collect(
    date: str,
    existing_rules: dict[str, list[str]],
    only_sites: set[str] | None = None,
    concurrency: int = 12,
    use_llm: bool = False,
    llm_model: str = "gpt-5.4-mini",
) -> tuple[dict[str, set[str]], dict[str, set[str]], Counter]:
    s3 = S3Client()
    raw_subtypes: dict[str, set[str]] = defaultdict(set)
    stats = Counter()

    sites = [site for site in MANIFESTS if not only_sites or site in only_sites]
    for site in sites:
        manifest = load_manifest(s3, site, date)
        stats["manifest_entries"] += len(manifest)
        allowed_brands = set(existing_rules)

        print(f"[SCAN] {site}: {len(manifest)} raw entries")
        with ThreadPoolExecutor(max_workers=max(1, concurrency)) as executor:
            futures = {
                executor.submit(scan_raw_entry, s3, entry, allowed_brands, use_llm, llm_model): entry
                for entry in manifest
            }
            for future in as_completed(futures):
                entry = futures[future]
                try:
                    brand, subtypes = future.result()
                except Exception as error:
                    stats["raw_read_errors"] += 1
                    print(f"[WARN] Failed raw scan for {entry.get('link', 'NA')}: {error}")
                    continue

                if not brand:
                    stats["missing_brand"] += 1
                    continue
                stats["raw_products"] += 1
                raw_subtypes.setdefault(brand, set())
                raw_subtypes[brand].update(subtypes)

    return raw_subtypes, stats


def column_name(index: int) -> str:
    name = ""
    while index:
        index, remainder = divmod(index - 1, 26)
        name = chr(65 + remainder) + name
    return name


def sheet_xml(rows: list[list[str]], column_widths: list[int]) -> str:
    sheet_rows = []
    for row_index, row in enumerate(rows, start=1):
        cells = []
        for column_index, value in enumerate(row, start=1):
            ref = f"{column_name(column_index)}{row_index}"
            style_index = 1 if row_index == 1 else 2
            cells.append(f'<c r="{ref}" s="{style_index}" t="inlineStr"><is><t>{escape(str(value))}</t></is></c>')
        height = ' ht="34" customHeight="1"' if row_index > 1 else ' ht="22" customHeight="1"'
        sheet_rows.append(f'<row r="{row_index}"{height}>{"".join(cells)}</row>')

    cols_xml = "".join(
        f'<col min="{index}" max="{index}" width="{width}" customWidth="1"/>'
        for index, width in enumerate(column_widths, start=1)
    )
    dimension = f"A1:{column_name(max(len(row) for row in rows))}{len(rows)}" if rows else "A1"
    return (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main" '
        'xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships">'
        f'<dimension ref="{dimension}"/>'
        '<sheetViews><sheetView workbookViewId="0"/></sheetViews>'
        '<sheetFormatPr defaultRowHeight="15"/>'
        f'<cols>{cols_xml}</cols>'
        f'<sheetData>{"".join(sheet_rows)}</sheetData>'
        '</worksheet>'
    )


def write_xlsx(output_path: Path, rows: list[list[str]]) -> None:
    content_types = """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">
  <Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>
  <Default Extension="xml" ContentType="application/xml"/>
  <Override PartName="/xl/workbook.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet.main+xml"/>
  <Override PartName="/xl/worksheets/sheet1.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.worksheet+xml"/>
  <Override PartName="/xl/styles.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.styles+xml"/>
</Types>"""
    root_rels = """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">
  <Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="xl/workbook.xml"/>
</Relationships>"""
    workbook = """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<workbook xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main"
  xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships">
  <sheets><sheet name="raw_sub_type_discovery" sheetId="1" r:id="rId1"/></sheets>
</workbook>"""
    workbook_rels = """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">
  <Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/worksheet" Target="worksheets/sheet1.xml"/>
  <Relationship Id="rId2" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/styles" Target="styles.xml"/>
</Relationships>"""
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
        workbook_zip.writestr("xl/worksheets/sheet1.xml", sheet_xml(rows, [28, 48, 120]))


def build_rows(existing_rules: dict[str, list[str]], raw_subtypes: dict[str, set[str]]) -> list[list[str]]:
    rows = [["brand", "sub_types", "all_sub_types"]]
    brands = sorted(existing_rules)
    for brand in brands:
        existing = existing_rules.get(brand, [])
        if is_excluded_brand(brand):
            continue
        raw = filter_subtypes(sorted(raw_subtypes.get(brand, set())), brand)
        existing_word_sets = [(value, set(value.split())) for value in existing if value != "regular"]
        raw = [
            value
            for value in raw
            if not any(
                value != existing_value
                and set(value.split())
                and set(value.split()) < existing_words
                for existing_value, existing_words in existing_word_sets
            )
        ]
        all_subtypes = dedupe(existing + raw, keep_regular=True)
        if not existing and not all_subtypes:
            continue
        rows.append(
            [
                brand,
                ", ".join(existing),
                ", ".join(all_subtypes),
            ]
        )
    return rows


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--date", required=True, help="Date to scan, e.g. 2026-05-27")
    parser.add_argument("--rules", type=Path, default=DEFAULT_RULES, help="Existing sub_type_rules.csv path")
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT, help="Output .xlsx path")
    parser.add_argument(
        "--only",
        action="append",
        default=[],
        help="Optional site key to scan. Can be passed multiple times.",
    )
    parser.add_argument("--concurrency", type=int, default=12, help="Raw S3 object read concurrency.")
    parser.add_argument("--use-llm", action="store_true", help="Also ask the LLM for subtype candidates.")
    parser.add_argument("--llm-model", default="gpt-5.4-mini", help="Model used with --use-llm.")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    only_sites = set(args.only) if args.only else None
    unknown_sites = (only_sites or set()) - set(MANIFESTS)
    if unknown_sites:
        raise SystemExit(f"Unknown --only site(s): {', '.join(sorted(unknown_sites))}")

    existing_rules = load_existing_rules(args.rules)
    raw_subtypes, stats = collect(
        args.date,
        existing_rules,
        only_sites,
        concurrency=args.concurrency,
        use_llm=args.use_llm,
        llm_model=args.llm_model,
    )
    rows = build_rows(existing_rules, raw_subtypes)
    write_xlsx(args.output, rows)
    print(
        f"Wrote {args.output.resolve()} with {len(rows) - 1} brands; "
        f"scanned {stats['raw_products']}/{stats['manifest_entries']} raw entries; "
        f"errors={stats['raw_read_errors']}; missing_brand={stats['missing_brand']}"
    )


if __name__ == "__main__":
    main()
