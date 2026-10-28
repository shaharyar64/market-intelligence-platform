import re
import base64
import csv
import html as html_lib
import json
import time
import requests
from pathlib import Path
from typing import Optional, Any
from concurrent.futures import ThreadPoolExecutor, as_completed
from urllib.parse import urljoin, urlparse, urlunparse

from dotenv import load_dotenv
from pydantic import BaseModel
from langchain_openai import ChatOpenAI
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import JsonOutputParser
from langchain_core.messages import HumanMessage

load_dotenv()

# ─── CONFIGURATION ────────────────────────────────────────────────────────────

CURRENCY_TO_USD = {
    "AED": 0.272,
    "BHD": 2.648,
}

PLATFORM_TO_CURRENCY = {
    # UAE → AED
    "dubaidutyfree":     "AED",
    "jmkcellars":        "AED",
    "citydrinks":        "AED",
    "gmp":               "AED",
    "royalspirit":       "AED",
    "unisatgt":          "AED",
    "windmillgt":        "AED",
    "thebottlestore":    "AED",
    "spinneysauh":       "AED",
    "highspiritsuae":    "AED",
    "centaurusint":      "AED",
    "africaneastern":    "AED",
    "mmihomedelivery":   "AED",
    "supercellar":       "AED",
    # Bahrain → BHD
    "africanandeastern": "BHD",
    "gbiexpress":        "BHD",
    "bmmishops":         "BHD",
    "nhsc":              "BHD",
    "bdutyfree":         "BHD",
}

# ─── KNOWN BRANDS ─────────────────────────────────────────────────────────────
# Canonical brand list — LLM normalizes to these spellings.
# If brand not in list, LLM still extracts it from the name directly.
# Add new brands here as you discover them across sites.
KNOWN_BRANDS = sorted(set([
    # Major international
    "heineken", "amstel", "carlsberg", "budweiser", "bud light", "corona", "stella artois",
    "beck's", "peroni", "hoegaarden", "leffe", "guinness", "kronenbourg",
    "tuborg", "efes", "sol", "modelo", "desperados", "blue moon", "tiger",

    # German
    "erdinger", "paulaner", "franziskaner", "weihenstephaner", "benediktiner",
    "krombacher", "bitburger", "warsteiner", "kaiserdom", "mecklenburger",
    "könig ludwig", "löwenbräu", "hofbrau", "schofferhofer", "dab",
    "starnberger", "edelhopfen", "vitalsberg", "zibert", "matz",

    # Belgian
    "delirium", "chouffe", "duvel", "chimay", "kasteel", "grimbergen",
    "affligem", "orval", "westmalle", "rochefort", "kwak", "st. bernardus",
    "la trappe", "petrus", "gulden draak", "piraat", "lindemans", "floris",
    "fruli", "wittekerke", "st. feuillien", "triple karmeliet", "pauwel kwak",
    "goudale", "bière des amis", "rochehaut", "filou", "la guillotine",
    "zundert", "tynt meadow", "malheur", "kristoffel", "bush", "maredsous",
    "two chefs", "texels", "moersleutel",

    # Czech / Eastern European
    "pilsner urquell", "staropramen", "budvar", "kozel", "bernard",
    "okocim", "baltika", "hollandia", "oranjeboom",

    # Spanish
    "estrella damm", "alhambra", "mahou", "moritz", "estrella galicia",
    "damm", "salitos",

    # UK / Irish
    "murphy's", "kilkenny", "o'hara's", "belhaven", "tennents",
    "greene king", "abbot", "old speckled hen", "hobgoblin", "brewdog",
    "thornbridge", "marston's", "rye river", "magners", "strongbow",
    "weston", "thatchers", "rekorderlig", "kopparberg", "crabbie's",
    "jaipur",

    # Italian
    "birra moretti", "angelo poretti",

    # Greek
    "mythos", "fix",

    # Turkish
    "bomonti",

    # Dutch
    "grolsch", "bavaria", "royal dutch",

    # African
    "savanna", "windhoek", "castle", "carling", "hunter's", "lion brewery",
    "simba", "buffelsfontein", "loxtonia", "devil's peak",

    # Indian subcontinent
    "kingfisher", "haywards", "bira", "kalyani", "godfather", "malayali",
    "red horse", "san miguel", "barahsinghe", "himalayan", "commando",

    # Japanese
    "kirin", "asahi", "sapporo",

    # Chinese
    "tsingtao",

    # Thai
    "chang", "singha", "leo",

    # Vietnamese
    "saigon",

    # Middle Eastern / regional
    "almaza", "beirut", "majlis", "oryx", "beer 66",

    # Australian
    "coopers", "pirate life", "kaiju",

    # American craft / mainstream
    "goose island", "sierra nevada", "samuel adams", "brooklyn", "michelob",
    "miller",

    # UAE / Bahrain local
    "royal spirit", "greenberg", "side hustle", "craft nation", "purple parrot",
    "grins", "mio", "cruise", "just life", "kamasutra", "swahill", "southan",
    "penguin", "shake", "snowy", "red rose", "8 horse", "mannilla", "maximus",

    # Cider
    "somersby", "kiss",

    # Other
    "dassai", "sho chiku bai", "shirakabegura",
    "bacardi", "smirnoff", "cody's", "mg", "oj", "cooler", "buzz",
    "wild star", "corelli", "heavensake", "choya",
    "bear", "manga", "manila", "tag", "ds strong",
]))

# ─── BRAND ALIASES ────────────────────────────────────────────────────────────
# Post-processing safety net for variations the LLM still gets wrong.
# LLM brand list is primary — this is secondary cleanup only.
# None = garbage brand → returned as "NA"
BRAND_ALIASES = {
    # ── Kaiju ─────────────────────────────────────────────────────────────────
    "kaiju!":                        "kaiju",

    # ── Garbage / invalid ─────────────────────────────────────────────────────
    "na":                            None,
    "n/a":                           None,
    "ok":                            None,
    "66":                            None,
    "x mark":                        None,
    "x mark vodka":                  None,
    "buzz vodka orange":             None,
    "revo energy":                   None,
    "manito mezcal":                 None,
    "good of san sebastian":         None,
    "kokki":                         None,
    "data not available":            None,
    "object":                        None,

    # ── TAG / DS Strong ──────────────────────────────────────────────────────
    "tag":                           "tag",
    "tag premium":                   "tag",
    "ds":                            "ds strong",
    "ds strong":                     "ds strong",

    # ── Kingfisher ────────────────────────────────────────────────────────────
    "king fisher":                   "kingfisher",
    "king-fisher":                   "kingfisher",
    "king fisher blue premium":      "kingfisher",
    "kingfisher blue premium":       "kingfisher",
    "kingfisher beer":               "kingfisher",
    "kingfisher's":                  "kingfisher",

    # ── Heineken ──────────────────────────────────────────────────────────────
    "heineken's":                    "heineken",
    "heinekin":                      "heineken",
    "heinken":                       "heineken",

    # ── Budweiser ─────────────────────────────────────────────────────────────
    "budwiser":                      "budweiser",
    "bud zero":                      "budweiser",
    "budweiser magnum":              "budweiser",

    # ── Bud Light ────────────────────────────────────────────────────────────
    "bud light":                     "bud light",

    # ── Budvar ───────────────────────────────────────────────────────────────
    "budejovicky":                   "budvar",
    "budejovicky budvar":            "budvar",
    "budweiser budvar":              "budvar",
    "budvar":                        "budvar",
    "budvar czech lager":            "budvar",
    "budvar original":               "budvar",

    # ── San Miguel ────────────────────────────────────────────────────────────
    "san miguel beer":               "san miguel",
    "san miguel light":              "san miguel",
    "san mig":                       "san miguel",
    "san mig light":                 "san miguel",
    "sanmiguel":                     "san miguel",
    "san-miguel":                    "san miguel",

    # ── Red Horse ─────────────────────────────────────────────────────────────
    "red-horse":                     "red horse",
    "redhorse":                      "red horse",

    # ── Guinness ──────────────────────────────────────────────────────────────
    "guiness":                       "guinness",
    "guinness's":                    "guinness",

    # ── Stella Artois ─────────────────────────────────────────────────────────
    "stella":                        "stella artois",

    # ── Hoegaarden ────────────────────────────────────────────────────────────
    "hoegarden":                     "hoegaarden",
    "hoegaargen":                    "hoegaarden",
    "hoegaarden rose":               "hoegaarden",
    "hoegaarden rosée":              "hoegaarden",

    # ── Amstel ────────────────────────────────────────────────────────────────
    "amstel light":                  "amstel",

    # ── Beck's ────────────────────────────────────────────────────────────────
    "becks":                         "beck's",
    "beck":                          "beck's",

    # ── Peroni ────────────────────────────────────────────────────────────────
    "peroni nastro azzurro":         "peroni",
    "peroni nastro azzuro":          "peroni",

    # ── Birra Moretti ─────────────────────────────────────────────────────────
    "birra moretti italian":         "birra moretti",
    "birra moretti italian lager":   "birra moretti",

    # ── Singha ────────────────────────────────────────────────────────────────
    "singha thai":                   "singha",
    "singha thai lager":             "singha",

    # ── König Ludwig ──────────────────────────────────────────────────────────
    "konig ludwig":                  "könig ludwig",

    # ── Löwenbräu ─────────────────────────────────────────────────────────────
    "lowenbrau":                     "löwenbräu",
    "lwenbru":                       "löwenbräu",
    "lowenbräu":                     "löwenbräu",

    # ── Kronenbourg ───────────────────────────────────────────────────────────
    "kronenbourg 1664":              "kronenbourg",
    "kronenbourg 1664 blanc":        "kronenbourg",

    # ── Tiger ─────────────────────────────────────────────────────────────────
    "tiger beer":                    "tiger",

    # ── DAB ───────────────────────────────────────────────────────────────────
    "dab diat":                      "dab",
    "dab diat pils":                 "dab",
    "dab diat silver":               "dab",
    "dab diat pils silver":          "dab",
    "dab dat":                       "dab",
    "dab dat pils":                  "dab",

    # ── Efes ──────────────────────────────────────────────────────────────────
    "efes pilsner":                  "efes",

    # ── Hunter's ──────────────────────────────────────────────────────────────
    "hunters":                       "hunter's",
    "hunters gold":                  "hunter's",
    "hunters' gold":                 "hunter's",
    "hunters hard lemon":            "hunter's",
    "hunter's hard lemon":           "hunter's",

    # ── Savanna ───────────────────────────────────────────────────────────────
    "savanna light":                 "savanna",
    "savanna dry angry lemon":       "savanna",

    # ── Greene King ───────────────────────────────────────────────────────────
    "greene king ipa":               "greene king",

    # ── Castle ────────────────────────────────────────────────────────────────
    "castle lite":                   "castle",

    # ── Carling ───────────────────────────────────────────────────────────────
    "carling black label":           "carling",

    # ── Smirnoff ──────────────────────────────────────────────────────────────
    "smirnoff ice":                  "smirnoff",

    # ── Estrella Damm ─────────────────────────────────────────────────────────
    "estrella damm daura":           "estrella damm",
    "estrella daura":                "estrella damm",
    "estrella galicia":              "estrella damm",
    
    # --daura dmm --------------------------------------------------------------
    "daura":                         "daura damm",
    "daura damm":                    "daura damm",

    # ── Erdinger ──────────────────────────────────────────────────────────────
    "erdinger brauhaus":             "erdinger",

    # ── O'Hara's ──────────────────────────────────────────────────────────────
    "oharas":                        "o'hara's",
    "o'haras":                       "o'hara's",
    "ohara":                         "o'hara's",
    "o'hara":                        "o'hara's",

    # ── Murphy's ──────────────────────────────────────────────────────────────
    "murphys irish stout":           "murphy's",
    "murphys":                       "murphy's",

    # ── Delirium ──────────────────────────────────────────────────────────────
    "delirium tremens":              "delirium",
    "delirium argentum":             "delirium",

    # ── Chouffe ───────────────────────────────────────────────────────────────
    "chouffe n'ice":                 "chouffe",
    "chouffe nice":                  "chouffe",
    "chouffe soleil":                "chouffe",
    "chouffe mcchouffe":             "chouffe",
    "chouffe mc chouffe":            "chouffe",
    "chouffe cherry":                "chouffe",
    "chouffe houblon":               "chouffe",
    "chouffe bok":                   "chouffe",
    "chouffe belgian blond ale":     "chouffe",

    # ── Kasteel ───────────────────────────────────────────────────────────────
    "kasteel rouge":                 "kasteel",
    "kasteel rubus framboise":       "kasteel",
    "kasteel barista":               "kasteel",
    "kasteel bruin":                 "kasteel",
    "kasteel tripel":                "kasteel",
    "kasteel cuvee du chateau":      "kasteel",

    # ── Leffe ─────────────────────────────────────────────────────────────────
    "leffe blond":                   "leffe",
    "leffe's":                       "leffe",
    "leffe blonde":                  "leffe",
    "leffe triple":                  "leffe",

    # ── Mannilla ──────────────────────────────────────────────────────────────
    "mannilla":                      "manila",
    "mannila":                       "manila",

    # ── Lion Brewery ──────────────────────────────────────────────────────────
    "lion":                          "lion brewery",
    "lion brewery ceylon plc":       "lion brewery",
    "lion brewery ceylon p":         "lion brewery",
    "lion brewery (ceylon) plc":     "lion brewery",

    # ── Al Maza / Almaza ──────────────────────────────────────────────────────
    "al maza":                       "almaza",

    # ── Mecklenburger ─────────────────────────────────────────────────────────
    "mecklenburger pilsener":        "mecklenburger",
    "mecklenburger weissbier":       "mecklenburger",

    # ── Crabbie's ─────────────────────────────────────────────────────────────
    "crabbies":                      "crabbie's",
    "crabbie":                       "crabbie's",

    # ── Miller ────────────────────────────────────────────────────────────────
    "miller genuine draft":          "miller",

    # ── Fix ───────────────────────────────────────────────────────────────────
    "fix hellas":                    "fix",

    # ── Michelob ──────────────────────────────────────────────────────────────
    "michelob ultra":                "michelob",

    # ── Mahou ─────────────────────────────────────────────────────────────────
    "mahou cinco estrellas":         "mahou",

    # ── Beer 66 ───────────────────────────────────────────────────────────────
    "beer 66 imported":              "beer 66",
    "beer 66 strong":                "beer 66",
    "66 imported":                   "beer 66",

    # ── Strongbow ─────────────────────────────────────────────────────────────
    "strongbow cider":               "strongbow",

    # ── Weston ────────────────────────────────────────────────────────────────
    "weston cider":                  "weston",

    # ── Side Hustle ───────────────────────────────────────────────────────────
    "side hustle brews spirits":     "side hustle",
    "side hustle brews & spirits":   "side hustle",
    "side hustle brews and spirits": "side hustle",

    # ── Haywards ──────────────────────────────────────────────────────────────
    "haywards 5000":                 "haywards",
    "hawards 5000":                  "haywards",

    # ── Bira ──────────────────────────────────────────────────────────────────
    "bira 91":                       "bira",

    # ── Kirin ─────────────────────────────────────────────────────────────────
    "kirin ichiban":                 "kirin",

    # ── Petrus ────────────────────────────────────────────────────────────────
    "red by petrus":                 "petrus",

    # ── Maximus ───────────────────────────────────────────────────────────────
    "maximus beer":                  "maximus",

    # ── Alhambra ──────────────────────────────────────────────────────────────
    "alhambra reserva 1925":         "alhambra",
    "alhambra reserve 1945":         "alhambra",
    "alhambra reserve roja":         "alhambra",

    # ── La Goudale ────────────────────────────────────────────────────────────
    "la goudale":                    "goudale",
    "la goudale grand cru":          "goudale",
    "la goudale ipa":                "goudale",

    # ── MG Spirit ─────────────────────────────────────────────────────────────
    "mg spirit":                     "mg",
    "mg spirit mojito":              "mg",
    "mg spirit vodka lime":          "mg",

    # ── OJ ────────────────────────────────────────────────────────────────────
    "o.j beer":                      "oj",
    "o.j":                           "oj",
    "oj strong":                     "oj",

    # ── Kalyani ───────────────────────────────────────────────────────────────
    "kalyani black label":           "kalyani",

    # ── Cooler ────────────────────────────────────────────────────────────────
    "cooler ginger dark cherry":     "cooler",
    "dark cherry":                   "cooler",

    # ── Bacardi ───────────────────────────────────────────────────────────────
    "bacardi breezer":               "bacardi",

    # ── Kiss ──────────────────────────────────────────────────────────────────
    "cider kiss":                    "kiss",
    "kiss cider":                    "kiss",

    # ── Malayali ──────────────────────────────────────────────────────────────
    "malayali power":                "malayali",

    # ── Majlis ────────────────────────────────────────────────────────────────
    "majlis arabian league":         "majlis",

    # ── Beirut ────────────────────────────────────────────────────────────────
    "beirut beer":                   "beirut",

    # ── Bière des Amis ────────────────────────────────────────────────────────
    "bire des amis":                 "bière des amis",

    # ── Cody's ────────────────────────────────────────────────────────────────
    "codys":                         "cody's",

    # ── Grins ─────────────────────────────────────────────────────────────────
    "grins kicker":                  "grins",

    # ── Abbot ─────────────────────────────────────────────────────────────────
    "abbot ale":                     "abbot",

    # ── Old Speckled Hen ─────────────────────────────────────────────────────
    "old specked hen":               "old speckled hen",

    # ── Rochefort ─────────────────────────────────────────────────────────────
    "rochefort 10":                  "rochefort",
    "rochefort 8":                   "rochefort",
    "rochefort 6":                   "rochefort",
    "rochefort tripel extra":        "rochefort",

    # ── St. Bernardus ─────────────────────────────────────────────────────────
    "st bernardus":                  "st. bernardus",
    "saint bernardus":               "st. bernardus",
    "st bernardus abt 12":           "st. bernardus",
    "st bernardus prior 8":          "st. bernardus",
    "st bernardus pater 6":          "st. bernardus",
    "st bernardus wit":              "st. bernardus",

    # ── Westmalle ─────────────────────────────────────────────────────────────
    "westmalle tripel":              "westmalle",
    "westmalle dubbel":              "westmalle",
    "westmalle extra":               "westmalle",

    # ── Pauwel Kwak ───────────────────────────────────────────────────────────
    "pauwels kwak":                  "pauwel kwak",

    # ── Triple Karmeliet ──────────────────────────────────────────────────────
    "karmeliet":                     "triple karmeliet",
    "karmeliet tripel":              "triple karmeliet",

    # ── Grimbergen ────────────────────────────────────────────────────────────
    "grimbergen dubbel":             "grimbergen",
    "grimbergen blond":              "grimbergen",

    # ── Thornbridge / Green Mountain ──────────────────────────────────────────
    "green mountain":                "thornbridge",

    # ── Oranjeboom ────────────────────────────────────────────────────────────
    "orangeboom":                    "oranjeboom",

    # ── Schofferhofer ─────────────────────────────────────────────────────────
    "schofferhofer hefe grapefruit": "schofferhofer",
    "schofferhofer hafeweizen":      "schofferhofer",

    # ── Sierra Nevada ─────────────────────────────────────────────────────────
    "sierra nevada pale ale":        "sierra nevada",
    "sierra nevada california ipa":  "sierra nevada",
}

# Precompute brand list string once — passed to LLM in every call
_BRAND_LIST_STR = ", ".join(KNOWN_BRANDS)

# Cache to avoid re-fetching same image URL multiple times
_image_pack_format_cache: dict = {}

# Max parallel workers for image detection
IMAGE_DETECTION_WORKERS = 5
IMAGE_DOWNLOAD_RETRY_ATTEMPTS = 3
IMAGE_DOWNLOAD_RETRY_DELAY_SECONDS = 1

SUB_TYPE_RULES_PATH = Path(__file__).resolve().parent / "sub_type_rules.csv"

SUB_TYPE_ALIASES = {
    "lite": "light",
    "stong": "strong",
    "ultramax": "ultra max",
    "ultra-max": "ultra max",
    "ultra_max": "ultra max",
    "no variant": "regular",
    "0": "0.0",
    "zero": "0.0",
    "zero zero": "0.0",
    "non alcoholic": "0.0",
    "non alcohol": "0.0",
    "cero": "cero",
}


def _normalize_rule_text(value: str) -> str:
    normalized = str(value or "").strip().lower()
    normalized = re.sub(r"[_-]+", " ", normalized)
    normalized = re.sub(r"\s+", " ", normalized).strip()
    return normalized


def _canonical_sub_type(value: str) -> str:
    normalized = _normalize_rule_text(value)
    if normalized in ("na", "n/a", "data not available", "none", ""):
        return "regular"
    normalized = SUB_TYPE_ALIASES.get(normalized, normalized)
    return "gold" if normalized == "golden" else normalized


def _brand_rule_keys(brand: str) -> set[str]:
    normalized = _normalize_rule_text(brand)
    keys = {normalized}
    possessive_stripped = re.sub(r"'s\b", "", normalized)
    if possessive_stripped != normalized:
        keys.add(possessive_stripped)
    compact = re.sub(r"[^a-z0-9]+", "", normalized)
    if compact:
        keys.add(compact)
    compact_possessive_stripped = re.sub(r"[^a-z0-9]+", "", possessive_stripped)
    if compact_possessive_stripped:
        keys.add(compact_possessive_stripped)
    return {key for key in keys if key}


def _append_unique(values: list[str], value: str) -> None:
    if value and value not in values:
        values.append(value)


def _load_sub_type_rules(path: Path) -> tuple[dict[str, list[str]], dict[str, dict[str, str]]]:
    if not path.exists():
        raise RuntimeError(f"Missing sub_type rules CSV: {path}")

    rules: dict[str, list[str]] = {}
    match_aliases: dict[str, dict[str, str]] = {}
    with path.open(newline="", encoding="utf-8-sig") as file:
        reader = csv.DictReader(file)
        expected_columns = {"cleaned_brand", "sub_types"}
        if not expected_columns.issubset(set(reader.fieldnames or [])):
            raise RuntimeError(
                f"{path} must contain columns: {', '.join(sorted(expected_columns))}"
            )

        for row in reader:
            brand = _normalize_rule_text(row.get("cleaned_brand", ""))
            raw_sub_types = [
                _normalize_rule_text(sub_type)
                for sub_type in str(row.get("sub_types", "")).split(",")
                if _normalize_rule_text(sub_type)
            ]
            if not brand or not raw_sub_types:
                continue

            for key in _brand_rule_keys(brand):
                brand_rules = rules.setdefault(key, [])
                brand_aliases = match_aliases.setdefault(key, {})

                for raw_sub_type in raw_sub_types:
                    # A CSV value such as "strong/special/red" means:
                    # output "strong", but allow "special" or "red" to match it.
                    parts = [
                        _canonical_sub_type(part)
                        for part in raw_sub_type.split("/")
                        if _canonical_sub_type(part)
                    ]
                    if not parts:
                        continue

                    canonical = parts[0]
                    _append_unique(brand_rules, canonical)
                    for part in parts:
                        brand_aliases[part] = canonical

    if not rules:
        raise RuntimeError(f"No sub_type rules loaded from {path}")
    return rules, match_aliases


BRAND_SUB_TYPE_RULES, BRAND_SUB_TYPE_MATCH_ALIASES = _load_sub_type_rules(SUB_TYPE_RULES_PATH)
ALL_ALLOWED_SUB_TYPES = set().union(*(set(values) for values in BRAND_SUB_TYPE_RULES.values()))
ORDERED_SUB_TYPE_CANDIDATES = sorted(
    ALL_ALLOWED_SUB_TYPES | set(SUB_TYPE_ALIASES) | {
        alias
        for aliases in BRAND_SUB_TYPE_MATCH_ALIASES.values()
        for alias in aliases
    },
    key=lambda value: (-len(value), value),
)

# ──────────────────────────────────────────────────────────────────────────────


class BeerProduct(BaseModel):
    platform: str
    product_name: str
    brand: str
    type: str
    sub_type: str
    quantity: str
    units: int
    pack_format: str
    original_price_local: Optional[float] = None
    original_price_usd: Optional[float] = None
    discounted_price_local: Optional[float] = None
    discounted_price_usd: Optional[float] = None
    currency: str
    discount_percentage: Optional[float] = None
    link: str
    image_link: str
    availability: str
    features_in_top10: str
    features_on_first_page: str


parser = JsonOutputParser(pydantic_object=BeerProduct)

SYSTEM_PROMPT = """\
You are a data extraction engine. Your only job is to extract beer/cider/keg product data from the raw input provided.

STRICT RULES:
- Extract ONLY what is explicitly present in the input.
- Do NOT infer, guess, assume, or hallucinate any values.
- Do NOT use your training knowledge to fill in missing fields.
- If a value is not clearly present, use "NA" for strings or null for numbers.
- Do NOT return any text outside the JSON array. No explanations, no markdown, no code fences.

INPUT TYPE: {{input_type}}
- If input_type is "html":
  * Prices are displayed visually on the page. The currency symbol is rendered by CSS and appears
    as a blank space before the number in the HTML text — it is NOT part of the price.
  * Extract the number EXACTLY as shown. " 120" -> 120, " 44.05" -> 44.05, " 7" -> 7.
  * THE NUMBER IS THE FINAL PRICE. Do NOT multiply or divide it.
  * BHD prices use 3 decimal places: "BD 71.000" means 71.0 BHD. Extract as 71.0.

- If input_type is "json":
  * Prices are stored as raw numbers in JSON fields.
  * Extract the price value EXACTLY as it appears in the JSON field.
  * Do NOT divide by 100. Do NOT multiply. Extract the number as-is.
  * Look for price fields such as: price, originalPrice, regularPrice, currentPrice,
    discountedPrice, salePrice, specialPrice, amount, value, or nested inside price objects.

SKIP RULES — Do NOT extract these products at all:
- Skip any product where the name, description, or slug contains "Draught" (case-insensitive).
- Skip any product that is clearly not a beer, cider, or keg (e.g. wine, spirits, whisky,
  vodka, rum, gin, mixers, water, snacks, draught tap systems).
- Keg products are valid — do NOT skip them.

FIELD EXTRACTION RULES:

1. platform:
   - For HTML: extract from domain in URLs, canonical tags, or og:url.
   - For JSON: extract from any domain/url field present, or use "NA".
   - Strip subdomain (e.g. "citydrinks" from citydrinks.com).

2. product_name:
   - Extract the full product title/name exactly as shown in the source product/SKU.
   - Keep brand, variant, quantity, pack size, and pack format words if they are part of the title.
   - Do NOT normalize, shorten, translate, or rewrite it.
   - If not found, use "NA".
   - Examples:
     * "Budweiser Beer Can 35.5cl (Case of 24)" -> "Budweiser Beer Can 35.5cl (Case of 24)"
     * "San Miguel Red Horse Beer 50cl (1 Can)" -> "San Miguel Red Horse Beer 50cl (1 Can)"

3. brand:
   - Extract the brand name from the product name/title field. If not clear there,
     try the description or slug/URL.
   - Lowercase only.
   - If the brand matches something in this known brand list, use the EXACT spelling from the list:
     {{brand_list}}
   - If the brand is NOT in the list, still extract it from the name using your best judgment.
   - Strip descriptors before matching: light, strong, draft, zero, premium, extra, super,
     pale, pilsen, pilsner, lager, ale, stout, porter, beer, cider, can, bottle, pack,
     magnum, special, classic, original, fresh, gold, red, blue, black, white, italian,
     thai, japanese, mexican, german, belgian, irish, czech, danish, dutch, australian.
   - Examples:
     * "San Miguel Light Bottler 6-pack" -> "san miguel"
     * "Tiger 6-pack" -> "tiger"
     * "Westmalle Tripel 6-pack" -> "westmalle"
     * "Two Chefs Green Bullet Beer" -> "two chefs"
     * "Salitos Blue Beer Bottle" -> "salitos"
     * "Bush Blond Tripel" -> "bush"
     * "Texels Stormbock" -> "texels"
     * "Moersleutel Motor Oil Beer" -> "moersleutel"
     * "Schofferhofer Hefe Grapefruit" -> "schofferhofer"
     * "Maredsous Blond" -> "maredsous"
     * "Jaipur IPA" -> "jaipur"
     * "Heineken Blade Keg 8L" -> "heineken"
   - Use "NA" ONLY if the brand is truly unidentifiable — not just because it is absent from the list.

4. type:
   - "beer" if explicitly labelled as beer, lager, ale, pilsen, pilsner, stout, porter, ipa,
     weizen, wit, blond, tripel, dubbel, bock.
   - "cider" if explicitly labelled as cider.
   - "other" if neither is mentioned.
   - If not in name, try description or slug.
   - Do NOT guess from brand name alone.

5. sub_type:
   - Extract the beer variant/sub-variant/sub-type ONLY from these sources, in this exact priority order:
     1. Product URL/slug
     2. Product title/name
   - Use lowercase only.
   - Do NOT use description, product details section, remaining content, image, category, or brand knowledge.
   - Do NOT invent sub_type from the LLM response. Post-processing keeps only values found
     in the product URL/slug or product title/name and allowed by sub_type_rules.csv.
   - Brand-specific sub_type values MUST follow sub_type_rules.csv strictly.
   - Do not output a sub_type value unless it is valid for that exact brand in sub_type_rules.csv.
   - Examples: "Kingfisher Strong Beer" -> "strong", "Kingfisher Blue" -> "blue",
     "Kingfisher Extra Strong" -> "strong", "Tuborg Special" -> "strong", "Tuborg red" -> "strong",
     "Kingfisher Ultra Max" -> "ultra max", "/products/kingfisher-blue-can" -> "blue",
     "Brewdog Punk IPA" -> "punk ipa", "Budweiser Magnum" -> "magnum",
     "Carlsberg Elephant" -> "elephant", "Castle Lite" -> "light",
     "Windhoek Premium Lager" -> "premium", "Carlsberg Elephant" -> "elephant",
   - If the matched source has "lite", return "light" only when "light" is valid for that brand in sub_type_rules.csv.
   - If no valid sub_type is found in URL or title/name, return "regular".

6. quantity:
   - Extract per-unit volume. For "24 x 500ml" extract 500ml only.
   - For kegs, extract the keg volume (e.g. "8L Keg" -> "800.0CL").
   - Convert to CL: 330ml -> "33.0CL", 500ml -> "50.0CL", 1L -> "100.0CL", 8L -> "800.0CL".
   - Some slugs omit or replace decimal separators: "473cl" and "47-3cl" mean "47.3CL"; "355cl" and "35-5cl" mean "35.5CL".
   - Alcohol percentage before volume is not quantity: "16-50cl" in "16% 50CL" means "50.0CL".
   - Titles may contain typos where the letter "o" replaces a zero: "5ocl" means "50.0CL" (never 195).
   - If not found in name, try description or slug.
   - If not found anywhere, use "NA".

7. units:
   - Extract pack size (e.g. "24 x 500ml" -> 24, "6-pack" -> 6, "4-pack" -> 4).
   - For kegs, units = 1.
   - If not in name, try description or slug.
   - Default to 1 if truly not mentioned anywhere. Do NOT guess.

8. pack_format:
   - Check the product NAME, DESCRIPTION, and URL/SLUG in that order.
   - "Can" if "can", "cans", or "tin" is found in any of those sources.
   - "Glass" if "bottle", "bottles", "btl", or "glass" is found in any of those sources.
   - "Keg" if "keg" or "barrel" is found in any of those sources.
   - If none is found in name, description, or URL/slug, use "NA".
   - Post-processing will detect pack format from the product image when "NA" is returned.

9. currency:
   - ONLY "AED" or "BHD" are valid. NEVER output any other currency.
   - UAE platforms -> "AED": dubaidutyfree, jmkcellars, citydrinks, gmp, royalspirit,
     unisatgt, windmillgt, thebottlestore, spinneysauh, highspiritsuae, centaurusint,
     africaneastern, mmihomedelivery, supercellar
   - Bahrain platforms -> "BHD": africanandeastern, gbiexpress, bmmishops, nhsc, bdutyfree
   - If domain not in list, look for "AED", "BHD" in the content.
   - Default to "AED" if still unclear.

10. original_price_local:
   - HTML: the crossed-out/original price shown visually. Extract number exactly as displayed.
   - JSON: the original/regular price field value. Extract exactly as stored in JSON.
   - If only one price exists, that is the original price.
   - BHD prices use 3 decimal places: "BD 71.000" -> 71.0, "BD 1.500" -> 1.5
   - If not found, use null.

11. discounted_price_local:
   - HTML: the current/sale price shown visually. Extract number exactly as displayed.
   - JSON: the current/discounted price field value. Extract exactly as stored in JSON.
   - If no discount exists, use same value as original_price_local.
   - If not found, use null.

12. original_price_usd: Always return null — calculated in post-processing.
13. discounted_price_usd: Always return null — calculated in post-processing.
14. discount_percentage: Always return null — calculated in post-processing.

15. link:
    - Full product URL. Construct absolute URL from relative paths if needed.
    - If not found, use "NA".

16. image_link:
    - Full image URL from img src, data-src, or first srcset URL.
    - Construct absolute URL if relative.
    - If not found, use "NA".

17. availability:
    - "yes" if add-to-cart button present or no stock warning.
    - "no" ONLY if explicitly "Out of Stock", "Unavailable", "Sold Out".
    - Default "yes" if unclear.

18. features_in_top10:
    - "yes" if product is within first 10 in source order, else "no".

19. features_on_first_page:
    - "yes" unless explicit pagination shows this is not page 1.

Return a JSON array of product objects. Even if only one product, wrap it in an array.
Do NOT return anything outside the JSON array.
"""

prompt = ChatPromptTemplate.from_messages([
    ("system", SYSTEM_PROMPT),
    ("human", (
        "Input type: {input_type}\n"
        "Extract all beer/cider/keg product data from this {input_type}.\n"
        "Remember:\n"
        "- Skip only draught tap-system/home-draught products.\n"
        "- Do NOT skip normal packaged products with 'Draft' in the brand/name, such as Miller Genuine Draft.\n"
        "- Keg products are valid — do NOT skip them.\n"
        "- Extract prices as raw numbers exactly as they appear — do NOT divide or multiply.\n"
        "- Only 'AED' or 'BHD' are valid currencies.\n"
        "- product_name: full product title/name exactly as shown in the source.\n"
        "- Brand: match from the known list if possible, otherwise extract directly from the name.\n"
        "- quantity: 24x473cl and 24x47-3cl mean 47.3CL; 355cl and 35-5cl mean 35.5CL; 16% 50cl means 50.0CL.\n"
        "- sub_type: check URL first, then title/name only. Do not use description/content. Use sub_type_rules.csv strictly. Default to regular if none.\n"
        "- pack_format: check name/description first, then URL/slug. Use 'NA' only if not found anywhere.\n"
        "- Use 'NA' for any string field that is truly unidentifiable.\n"
        "- Return only a valid JSON array, nothing else.\n\n"
        "{html_content}"
    )),
])

# ── Models ────────────────────────────────────────────────────────────────────
# gpt-4.1-mini: text extraction — reliable, proven for structured extraction
# gpt-5-mini: vision/image detection — better vision capability
TEXT_MODEL = "gpt-5.4-mini"
VISION_MODEL = "gpt-5.4-mini"

llm = ChatOpenAI(
    model=TEXT_MODEL,
    temperature=0,
    timeout=90,
    max_retries=2,
)

vision_llm = ChatOpenAI(
    model=VISION_MODEL,
    temperature=0,
    timeout=60,
    max_retries=1,
)

chain = prompt | llm | parser


# ─── HELPERS ──────────────────────────────────────────────────────────────────

def _normalize_brand(brand: str) -> str:
    """
    Post-processing brand cleanup.
    LLM brand list is primary — this handles edge cases the LLM still gets wrong.
    """
    if not brand:
        return "NA"
    if brand.strip().lower() in ("na", "n/a", "data not available", ""):
        return "NA"
    normalized = brand.strip().lower()
    normalized = re.sub(r"'s$|`s$", "", normalized)
    normalized = re.sub(r"\s+", " ", normalized).strip()
    if normalized in BRAND_ALIASES:
        result = BRAND_ALIASES[normalized]
        return "NA" if result is None else result
    return normalized


def _normalize_sub_type(sub_type: str) -> str:
    """Normalize a candidate sub_type token into a stable lowercase value."""
    if not sub_type:
        return "regular"

    return _canonical_sub_type(sub_type)


def _allowed_sub_types_for_brand(brand: str) -> list[str]:
    for key in _brand_rule_keys(brand):
        if key in BRAND_SUB_TYPE_RULES:
            return BRAND_SUB_TYPE_RULES[key]
    return ["regular"]


def _sub_type_match_aliases_for_brand(brand: str) -> dict[str, str]:
    aliases: dict[str, str] = {}
    for key in _brand_rule_keys(brand):
        aliases.update(BRAND_SUB_TYPE_MATCH_ALIASES.get(key, {}))
    return aliases


def _visible_text_from_content(content: str) -> str:
    """Convert HTML-ish product content to normalized visible text."""
    text = re.sub(r"<(script|style)\b[^>]*>.*?</\1>", " ", content, flags=re.I | re.S)
    text = re.sub(r"<[^>]+>", " ", text)
    text = html_lib.unescape(text)
    text = re.sub(r"[_-]+", " ", text)
    return re.sub(r"\s+", " ", text).strip().lower()


def _clean_visible_text(content: str) -> str:
    """Convert HTML-ish product content to readable text while preserving casing."""
    text = re.sub(r"<(script|style)\b[^>]*>.*?</\1>", " ", content, flags=re.I | re.S)
    text = re.sub(r"<[^>]+>", " ", text)
    text = html_lib.unescape(text)
    return re.sub(r"\s+", " ", text).strip()


def _match_text(value: str) -> str:
    normalized = html_lib.unescape(str(value or "")).lower()
    normalized = re.sub(r"[_/%?=&.#:+-]+", " ", normalized)
    normalized = re.sub(r"[^a-z0-9' ]+", " ", normalized)
    return re.sub(r"\s+", " ", normalized).strip()


def _brand_from_text(*texts: str) -> str:
    combined = _match_text(" ".join(str(text or "") for text in texts))
    if not combined:
        return "NA"

    if re.search(r"\bds\s+strong\b", combined):
        return "ds strong"

    for brand in sorted(KNOWN_BRANDS, key=len, reverse=True):
        candidate = _match_text(brand)
        if candidate and re.search(rf"(?<![a-z0-9]){re.escape(candidate)}(?![a-z0-9])", combined):
            return _normalize_brand(brand)

    return "NA"


def _remove_sub_type_traps(text: str) -> str:
    """Remove product/brand lines that look like subtype tokens."""
    text = re.sub(r"\bred\s+horse\b", " ", text)
    return re.sub(r"\s+", " ", text).strip()


def _html_snippets_by_tag(content: str, tag: str) -> list[str]:
    return re.findall(rf"<{tag}\b[^>]*>(.*?)</{tag}>", content, flags=re.I | re.S)


def _html_snippets_by_class(content: str, class_pattern: str) -> list[str]:
    pattern = rf"<[^>]*class=['\"][^'\"]*{class_pattern}[^'\"]*['\"][^>]*>(?P<inner>.*?)</[^>]+>"
    return [
        match.group("inner")
        for match in re.finditer(pattern, content, flags=re.I | re.S)
    ]


def _extract_json_title_fields(content: str) -> str:
    try:
        data = json.loads(content)
    except Exception:
        return ""

    title_values: list[str] = []
    title_keys = {
        "title",
        "name",
        "product_name",
        "productname",
        "productTitle",
        "product_title",
        "display_name",
    }

    def _walk(value: Any):
        if isinstance(value, dict):
            for key, child in value.items():
                if str(key) in title_keys and isinstance(child, (str, int, float)):
                    title_values.append(str(child))
                else:
                    _walk(child)
        elif isinstance(value, list):
            for child in value:
                _walk(child)

    _walk(data)
    return " ".join(title_values)


def _extract_json_product_name(content: str) -> str:
    try:
        data = json.loads(content)
    except Exception:
        return ""

    title_keys = {
        "title",
        "name",
        "product_name",
        "productname",
        "productTitle",
        "product_title",
        "display_name",
    }

    def _walk(value: Any) -> str:
        if isinstance(value, dict):
            for key, child in value.items():
                if str(key) in title_keys and isinstance(child, (str, int, float)):
                    return str(child)
            for child in value.values():
                found = _walk(child)
                if found:
                    return found
        elif isinstance(value, list):
            for child in value:
                found = _walk(child)
                if found:
                    return found
        return ""

    return _walk(data)


def _extract_product_name_from_content(content: str) -> str:
    title_snippets: list[str] = []
    title_snippets.extend(_html_snippets_by_tag(content, "h1"))
    title_snippets.extend(_html_snippets_by_tag(content, "h2"))
    title_snippets.extend(_html_snippets_by_class(content, r"(product[-_\s]*title|product_title|title|name)"))
    title_snippets.append(_extract_json_product_name(content))

    for snippet in title_snippets:
        name = _clean_visible_text(snippet)
        if name:
            return name
    return "NA"


def _extract_title_from_content(content: str) -> str:
    title_snippets: list[str] = []
    title_snippets.extend(_html_snippets_by_tag(content, "h1"))
    title_snippets.extend(_html_snippets_by_tag(content, "h2"))
    title_snippets.extend(_html_snippets_by_class(content, r"(product[-_\s]*title|product_title|title|name)"))
    title_snippets.append(_extract_json_title_fields(content))
    return " ".join(_visible_text_from_content(snippet) for snippet in title_snippets if snippet)


def _sub_type_from_text(text: str, brand: str) -> str:
    text = _remove_sub_type_traps(_visible_text_from_content(text))
    if not text:
        return "NA"

    allowed = set(_allowed_sub_types_for_brand(brand))
    if brand == "kingfisher" and "blue" in allowed:
        blue_patterns = [
            r"(?<![a-z0-9])blue(?:[-_\s]+premium)?(?![a-z0-9])",
            r"(?<![a-z0-9])premium[-_\s]+blue(?![a-z0-9])",
        ]
        if any(re.search(pattern, text) for pattern in blue_patterns):
            return "blue"

    brand_match_aliases = _sub_type_match_aliases_for_brand(brand)
    for candidate in ORDERED_SUB_TYPE_CANDIDATES:
        canonical = brand_match_aliases.get(_normalize_sub_type(candidate), _normalize_sub_type(candidate))
        if canonical not in allowed:
            continue
        candidate_pattern = re.escape(candidate).replace(r"\ ", r"[-_\s]+")
        pattern = rf"(?<![a-z0-9]){candidate_pattern}(?![a-z0-9])"
        if re.search(pattern, text):
            return canonical

    return "NA"


def _default_sub_type_for_brand(brand: str) -> str:
    """
    Final CSV-only fallback.
    If the brand has exactly one allowed sub_type, use it. Otherwise prefer
    "regular" when the CSV allows it, then fall back to the first CSV value.
    """
    allowed = _allowed_sub_types_for_brand(brand)
    if len(allowed) == 1:
        return allowed[0]
    if "regular" in allowed:
        return "regular"
    return allowed[0] if allowed else "regular"


def _resolve_sub_type(product: dict, html_content: str = "", source_url: str = "") -> str:
    """
    Resolve sub_type deterministically from URL first, then product title/name only.
    Description, image URLs, general content, and the LLM sub_type value are intentionally ignored.
    """
    brand = _normalize_brand(product.get("brand", ""))
    url_text = " ".join([
        source_url,
        str(product.get("link", "")),
    ])
    sub_type = _sub_type_from_text(url_text, brand)
    if sub_type != "NA":
        return sub_type

    title_text = str(product.get("product_name", "")).strip()
    if title_text.lower() in ("", "na", "n/a", "data not available"):
        title_text = _extract_title_from_content(html_content)

    title_sub_type = _sub_type_from_text(title_text, brand)
    if title_sub_type != "NA":
        return title_sub_type

    return _default_sub_type_for_brand(brand)


def _clean_price(value: Any) -> Optional[float]:
    """Strip formatting only. Never divide or multiply."""
    if value is None:
        return None
    raw = str(value).strip()
    if not raw:
        return None
    cleaned = re.sub(r"[^\d.,]", "", raw)
    if not cleaned:
        return None
    if "," in cleaned and "." not in cleaned:
        cleaned = cleaned.replace(",", ".")
    elif "," in cleaned and "." in cleaned:
        cleaned = cleaned.replace(",", "")
    try:
        return round(float(cleaned), 2)
    except ValueError:
        return None


def _resolve_currency(product: dict) -> str:
    platform = str(product.get("platform", "")).lower().strip()
    if platform in PLATFORM_TO_CURRENCY:
        return PLATFORM_TO_CURRENCY[platform]
    extracted = str(product.get("currency", "")).upper().strip()
    if extracted in CURRENCY_TO_USD:
        return extracted
    print(f"[WARN] Unknown platform '{platform}', defaulting currency to AED")
    return "AED"


def _scope_text(product: dict, source_url: str = "") -> str:
    return " ".join(str(value).lower() for value in [
        product.get("product_name", ""),
        product.get("brand", ""),
        product.get("type", ""),
        product.get("sub_type", ""),
        product.get("link", ""),
        product.get("image_link", ""),
        source_url,
    ] if value)


def _has_draught_system_text(text: str) -> bool:
    patterns = [
        r"\bhome\s+draught\b",
        r"\bdraught\s+system\b",
        r"\bdraught\s+tap\b",
        r"\btap\s+system\b",
        r"\bblade\s+home\b",
        r"\bblade\b.*\bsystem\b",
        r"\bbeer\s+blade\b",
    ]
    return any(re.search(pattern, text) for pattern in patterns)


def _is_draught(product: dict) -> bool:
    """Skip draught tap-system/home-draught products. Standalone kegs remain valid."""
    fields_to_check = [
        product.get("product_name", ""),
        product.get("brand", ""),
        product.get("link", ""),
        product.get("image_link", ""),
    ]
    text = " ".join(str(field).lower() for field in fields_to_check if field)
    return _has_draught_system_text(text)


def _is_non_alcoholic(product: dict, source_url: str = "") -> bool:
    """Skip non-alcoholic beer/cider SKUs; they are outside pricing scope."""
    combined = _scope_text(product, source_url)

    non_alcoholic_patterns = [
        r"\bnon[-\s/]*alco(?:holic)?\b",
        r"\balcohol[-\s]*free\b",
        r"\bzero[-\s]*alcohol\b",
        r"\b0\.0\b",
        r"\bzero\s+zero\b",
        r"\bcero\b",
    ]

    return any(re.search(pattern, combined) for pattern in non_alcoholic_patterns)


def _is_out_of_scope_product(product: dict, source_url: str = "") -> bool:
    """Skip non beer/cider RTD/spirit products from mixed category pages."""
    combined = _scope_text(product, source_url)

    out_of_scope_patterns = [
        r"\bhome\s+draught\b",
        r"\bdraught\s+system\b",
        r"\bdraught\s+tap\b",
        r"\btap\s+system\b",
        r"\bblade\s+home\b",
        r"\bblade\b.*\bsystem\b",
        r"\bbeer\s+blade\b",
        r"\bvodka\b",
        r"\bwhisk(?:y|ey)\b",
        r"\bscotch\b",
        r"\brum\b",
        r"\btequila\b",
        r"\bliqueur\b",
        r"\bshochu\b",
        r"\bsoju\b",
        r"\bsake\b",
        r"\bjunmai\b",
        r"\bdaiginjo\b",
        r"\bginjo\b",
        r"\bdassai\b",
        r"\bchoya\b",
        r"\bgin\s+tonic\b",
        r"\bcocktail\b",
        r"\bmg[-\s]*spirit\b",
        r"\bbacardi\s+breezer\b",
        r"\b__trashed\b",
    ]

    return any(re.search(pattern, combined) for pattern in out_of_scope_patterns)


def _pack_format_from_text(*texts: str) -> str:
    """
    Extract pack format from any text — link, slug, image filename.
    Used as fallback between LLM extraction and image detection.
    Priority: Can > Glass > Keg > NA
    """
    combined = " ".join(str(t).lower() for t in texts if t)

    if re.search(r'\bcan\b|\bcans\b|\btin\b|\btins\b', combined):
        return "Can"

    if re.search(r'\bbottle\b|\bbottles\b|\bbtl\b|\bbtls\b|\bglass\b|\blongneck\b|\blong.neck\b', combined):
        return "Glass"

    if re.search(r'\bkeg\b|\bkegs\b|\bbarrel\b|\bbarrels\b', combined):
        return "Keg"

    return "NA"


def _quantity_from_text(*texts: str) -> str:
    combined = " ".join(str(text).lower() for text in texts if text)
    combined = re.sub(
        r"(?<=x)(\d+)[-_](\d+)\s*(ml|cl|l)\b",
        r"\1.\2\3",
        combined,
    )
    combined = re.sub(
        r"(?<![\dx])\b([2-9]\d)[-_](\d)\s*(ml|cl|l)\b",
        r"\1.\2\3",
        combined,
    )
    combined = re.sub(r"(?<=\d)\s*(l|cl|ml)\b", r"\1", combined)

    matches = re.findall(r"(\d+(?:\.\d+)?)\s*(ml|cl|l)\b", combined)
    if not matches:
        return "NA"

    amount_text, unit = matches[-1]
    amount = float(amount_text)

    if unit == "ml":
        cl = amount / 10
    elif unit == "l":
        cl = amount * 100
    elif "." not in amount_text and amount >= 200:
        cl = amount / 10
    else:
        cl = amount

    return f"{round(cl, 1)}CL"


def _quantity_from_product_details(content: str) -> str:
    text = _clean_visible_text(content)
    labeled_values = []
    for label in ("packing", "packaging", "volume", "size", "capacity"):
        labeled_values.extend(
            match.group(1)
            for match in re.finditer(
                rf"\b{label}\s*:\s*([^:]+?)(?=\s+(?:product\s+code|country|packing|packaging|volume|size|capacity|alcohol|ingredients)\s*:|$)",
                text,
                flags=re.I,
            )
        )

    for value in labeled_values:
        quantity = _quantity_from_text(value)
        if quantity != "NA":
            return quantity

    return "NA"


def _detect_pack_format_from_image(image_url: str, name_hint: str = "") -> str:
    """
    Download product image and use vision LLM to detect pack format.
    name_hint: product name or slug to help disambiguate edge cases.
    Results cached by URL to avoid duplicate calls.
    """
    if image_url in _image_pack_format_cache:
        return _image_pack_format_cache[image_url]

    try:
        if image_url.startswith("//"):
            image_url = f"https:{image_url}"
        elif image_url.startswith("/"):
            base_url = name_hint if str(name_hint).startswith("http") else "https://www.dubaidutyfree.com"
            image_url = urljoin(base_url, image_url)

        parsed_image_url = urlparse(image_url)
        if (
            "dubaidutyfree.com" in str(name_hint)
            and parsed_image_url.path.startswith("/ccstore/")
            and parsed_image_url.netloc
            and "dubaidutyfree.com" not in parsed_image_url.netloc
        ):
            image_url = urlunparse(
                parsed_image_url._replace(
                    scheme="https",
                    netloc="www.dubaidutyfree.com",
                )
            )

        print(f"[IMAGE] Detecting pack format: {image_url}")

        headers = {
            "User-Agent": (
                "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/146.0.0.0 Safari/537.36"
            ),
            "Accept": "image/webp,image/png,image/jpeg,image/gif,image/*;q=0.8,*/*;q=0.5",
            "Accept-Language": "en-US,en;q=0.9",
        }

        if str(name_hint).startswith("http"):
            headers["Referer"] = name_hint

        img_response = None
        retryable_statuses = {408, 429, 500, 502, 503, 504}
        for attempt in range(1, IMAGE_DOWNLOAD_RETRY_ATTEMPTS + 1):
            try:
                img_response = requests.get(image_url, headers=headers, timeout=15)
                if img_response.status_code == 200:
                    break

                print(
                    f"[IMAGE] Download attempt {attempt}/{IMAGE_DOWNLOAD_RETRY_ATTEMPTS} "
                    f"failed — status {img_response.status_code}"
                )
                if img_response.status_code not in retryable_statuses:
                    return "NA"
            except requests.RequestException as e:
                print(
                    f"[IMAGE] Download attempt {attempt}/{IMAGE_DOWNLOAD_RETRY_ATTEMPTS} "
                    f"failed: {e}"
                )

            if attempt < IMAGE_DOWNLOAD_RETRY_ATTEMPTS:
                time.sleep(IMAGE_DOWNLOAD_RETRY_DELAY_SECONDS * attempt)

        if not img_response or img_response.status_code != 200:
            print("[IMAGE] Failed to download after retries")
            return "NA"

        image_bytes = img_response.content
        content_type = img_response.headers.get("Content-Type", "").lower()

        if image_bytes.startswith(b"\xff\xd8\xff"):
            content_type = "image/jpeg"
        elif image_bytes.startswith(b"\x89PNG\r\n\x1a\n"):
            content_type = "image/png"
        elif image_bytes.startswith((b"GIF87a", b"GIF89a")):
            content_type = "image/gif"
        elif image_bytes.startswith(b"RIFF") and image_bytes[8:12] == b"WEBP":
            content_type = "image/webp"
        elif "jpeg" in content_type or "jpg" in content_type:
            content_type = "image/jpeg"
        elif "png" in content_type:
            content_type = "image/png"
        elif "gif" in content_type:
            content_type = "image/gif"
        elif "webp" in content_type:
            content_type = "image/webp"
        else:
            print(f"[IMAGE] Unsupported downloaded image format: {content_type or 'unknown'}")
            return "NA"

        image_b64 = base64.b64encode(image_bytes).decode("utf-8")

        image_payload = {
            "type": "image_url",
            "image_url": {
                "url": f"data:{content_type};base64,{image_b64}"
            }
        }

        hint_text = f"\nProduct name hint: '{name_hint}'" if name_hint else ""

        def _ask_vision(extra_instruction: str = "") -> str:
            msg = HumanMessage(content=[
                image_payload,
                {
                    "type": "text",
                    "text": (
                        "Look at this product image carefully.\n\n"
                        "IDENTIFICATION GUIDE:\n"
                        "- CAN: Metal container, cylindrical, pull-tab or pop-top lid on top.\n"
                        "  * Key feature: TOP IS WIDE — same width as body, no narrowing.\n"
                        "  * Made of aluminium/steel, often has ribbed bottom edge.\n"
                        "  * Even if it has printed label designs, if it has NO NECK it is a CAN.\n\n"
                        "- GLASS: Glass bottle with a NARROW NECK at the top.\n"
                        "  * Key feature: TOP IS NARROW — body widens below the neck.\n"
                        "  * Has a bottle cap, cork, or crown cap at the very top.\n"
                        "  * Transparent, green, brown, or dark colored glass.\n\n"
                        "- KEG: Large silver/metal barrel, much bigger than a can.\n"
                        "  * Has handles, dispensing tap, or is clearly barrel-shaped.\n"
                        "  * Much taller and wider than a regular can.\n\n"
                        "DECISION RULES — apply in order:\n"
                        "1. If the image is a BOX/CARTON/CASE and visible text says BOTTLES, BTL, or GLASS -> GLASS\n"
                        "2. If the image is a BOX/CARTON/CASE and visible text says CANS, CAN, or TINS -> CAN\n"
                        "3. Does the container have a NARROW NECK (tapers at top)? -> GLASS\n"
                        "4. Is the top as wide as the body (no narrowing)? -> CAN\n"
                        "5. Is it a large metal barrel with handles/tap? -> KEG\n"
                        "6. Is the image a BOX or CARTON without readable text? Look INSIDE at the containers.\n"
                        "7. Are BOTH can and bottle visible? Pick the PRIMARY/larger item.\n"
                        f"{hint_text}\n"
                        f"{extra_instruction}\n"
                        "Reply with ONLY one of: 'Can', 'Glass', 'Keg', 'NA'\n"
                        "No explanation. No other text."
                    )
                }
            ])
            result = vision_llm.invoke([msg])
            answer = result.content.strip().lower()
            if answer == "can":
                return "Can"
            elif answer == "glass":
                return "Glass"
            elif answer == "keg":
                return "Keg"
            else:
                return "NA"

        # First attempt
        pack_format = _ask_vision()

        # If uncertain, retry once with stronger instruction
        if pack_format == "NA":
            print(f"[IMAGE] Uncertain — retrying with stronger prompt...")
            pack_format = _ask_vision(
                "IMPORTANT: Make your best determination based on the container shape. "
                "Only reply 'NA' if the image is completely unrecognizable or corrupted."
            )

        print(f"[IMAGE] Detected: {pack_format}")
        _image_pack_format_cache[image_url] = pack_format
        return pack_format

    except Exception as e:
        print(f"[IMAGE] Detection failed: {e}")
        return "NA"

def _needs_pack_detection(product: dict) -> bool:
    """Check if pack format still needs to be determined."""
    pack_format = product.get("pack_format", "NA")
    return pack_format in ("NA", "data not available", "Glass or keg", None, "")


def _pack_format_has_text_support(product: dict) -> bool:
    text_pack = _pack_format_from_text(
        product.get("product_name", ""),
        product.get("link", ""),
    )
    return text_pack != "NA" and text_pack == product.get("pack_format")


def _resolve_availability(product: dict, html_content: str = "") -> str:
    """
    Resolve availability with the same contract used by QC.
    Default yes unless the source explicitly shows an out-of-stock state.
    """
    combined = " ".join(str(value).lower() for value in [
        product.get("availability", ""),
        product.get("product_name", ""),
        product.get("link", ""),
        html_content,
    ] if value)
    combined = re.sub(r"\s+", " ", combined)

    negative_patterns = [
        r"\bout\s+of\s+stock\b",
        r"\bsold\s+out\b",
        r"\bunavailable\b",
        r"\bcurrently\s+unavailable\b",
        r"\bnotify\s+me\s+when\s+in\s+stock\b",
    ]
    if any(re.search(pattern, combined) for pattern in negative_patterns):
        return "no"

    positive_patterns = [
        r"\badd\s+to\s+(cart|basket)\b",
        r"\bin\s+stock\b",
        r"\bavailable\b",
    ]
    if any(re.search(pattern, combined) for pattern in positive_patterns):
        return "yes"

    return "yes"


CIDER_BRAND_HINTS = {
    "blackthorn",
    "crabbie's",
    "henry westons",
    "hunter's",
    "kiss",
    "kopparberg",
    "loxtonia",
    "magners",
    "rekorderlig",
    "savanna",
    "somersby",
    "strongbow",
    "thatchers",
    "weston",
}

NON_BEER_BRAND_HINTS = {
    "bacardi",
    "buzz",
    "choya",
    "cody's",
    "cooler",
    "corelli",
    "dassai",
    "grins",
    "heavensake",
    "mg",
    "shirakabegura",
    "sho chiku bai",
    "smirnoff",
    "wild star",
    "x mark",
}

BEER_BRAND_HINTS = set(KNOWN_BRANDS) - CIDER_BRAND_HINTS - NON_BEER_BRAND_HINTS


def _contains_phrase(text: str, phrase: str) -> bool:
    normalized_text = _match_text(text)
    normalized_phrase = _match_text(phrase)
    if not normalized_text or not normalized_phrase:
        return False
    return bool(re.search(rf"(?<![a-z0-9]){re.escape(normalized_phrase)}(?![a-z0-9])", normalized_text))


def _resolve_type(product: dict, html_content: str = "", source_url: str = "") -> str:
    title_url_text = " ".join(str(value).lower() for value in [
        product.get("product_name", ""),
        product.get("link", ""),
        source_url,
    ] if value)
    combined = f"{title_url_text} {str(html_content).lower()}"
    combined = re.sub(r"\s+", " ", combined)

    beer_patterns = [
        r"\bbeer(?:s)?\b",
        r"\blager\b",
        r"\bale\b",
        r"\bpilsen\b",
        r"\bpilsner\b",
        r"\bstout\b",
        r"\bporter\b",
        r"\bipa\b",
        r"\bpale\b",
        r"\bweizen\b",
        r"\bwit\b",
        r"\bblond(?:e)?\b",
        r"\btripel\b",
        r"\bdubbel\b",
        r"\bbock\b",
    ]

    if re.search(r"\bcider\b", title_url_text):
        return "cider"

    if any(_contains_phrase(title_url_text, brand) for brand in CIDER_BRAND_HINTS):
        return "cider"

    if any(re.search(pattern, title_url_text) for pattern in beer_patterns):
        return "beer"

    if any(_contains_phrase(title_url_text, brand) for brand in BEER_BRAND_HINTS):
        return "beer"

    other_patterns = [
        r"\bwhisk(?:y|ey)\b",
        r"\bscotch\b",
        r"\bvodka\b",
        r"\bgin\b",
        r"\brum\b",
        r"\btequila\b",
        r"\bcocktail\b",
        r"\bsake\b",
        r"\bjunmai\b",
        r"\bdaiginjo\b",
        r"\bginjo\b",
        r"\bdassai\b",
        r"\bchoya\b",
    ]
    if any(re.search(pattern, combined) for pattern in other_patterns):
        return "other"

    if any(re.search(pattern, combined) for pattern in beer_patterns):
        return "beer"

    if re.search(r"\bcider\b", combined) and not re.search(r"\bbeer\s+and\s+cider\b", combined):
        return "cider"

    if re.search(r"\brtd\b", title_url_text):
        return "other"

    return "other"


def _process_product(
    product: dict,
    input_type: str = "html",
    html_content: str = "",
    source_url: str = "",
) -> dict:
    """
    Process a single product:
    1. Fill product_name fallback from source title/name
    2. Normalize brand via aliases (secondary cleanup after LLM brand list)
    3. Normalize sub_type into stable lowercase values
    4. Resolve currency
    5. Clean price formatting — NO division or multiplication
       Each scraper is responsible for converting prices to correct units
       before calling parse_html_code. data_extractor trusts prices as-is.
    6. Compute USD prices and discount %
    7. Fallback pack format from link/slug if LLM returned NA
    """
    # Step 1: Fill full source product name
    product_name = str(product.get("product_name", "")).strip()
    if product_name.lower() in ("", "na", "n/a", "data not available"):
        product_name = _extract_product_name_from_content(html_content)
    product["product_name"] = product_name or "NA"

    # Step 2: Normalize brand
    product["brand"] = _normalize_brand(product.get("brand", ""))
    if product["brand"] == "NA":
        product["brand"] = _brand_from_text(
            product.get("product_name", ""),
            source_url,
            product.get("link", ""),
            html_content,
        )

    # Step 3: Resolve type from category/title/slug with spirit RTD guards.
    product["type"] = _resolve_type(product, html_content=html_content, source_url=source_url)

    # Step 4: Resolve sub_type from product URL first, then product title/name only
    product["sub_type"] = _resolve_sub_type(product, html_content=html_content, source_url=source_url)

    # Step 5: Resolve currency from hardcoded platform map
    currency = _resolve_currency(product)
    product["currency"] = currency
    multiplier = CURRENCY_TO_USD[currency]

    # Step 5: Clean price formatting only — no math
    # Scrapers are responsible for their own price unit conversion before calling us
    orig = _clean_price(product.get("original_price_local"))
    disc = _clean_price(product.get("discounted_price_local"))

    # Step 6: Default discounted to original if missing
    if disc is None:
        disc = orig

    # Step 7: Store final prices and compute USD + discount
    product["original_price_local"] = orig
    product["discounted_price_local"] = disc
    product["original_price_usd"] = round(orig * multiplier, 2) if orig is not None else None
    product["discounted_price_usd"] = round(disc * multiplier, 2) if disc is not None else None

    if orig and disc and orig > 0 and disc < orig:
        product["discount_percentage"] = round((orig - disc) / orig * 100, 2)
    else:
        product["discount_percentage"] = 0.0

    # Step 8: Resolve quantity deterministically from title/link first, then product HTML.
    quantity_from_title = _quantity_from_text(product.get("product_name", ""), source_url, product.get("link", ""))
    if quantity_from_title != "NA":
        product["quantity"] = quantity_from_title
    else:
        quantity_from_html = _quantity_from_product_details(html_content)
        if quantity_from_html == "NA":
            quantity_from_html = _quantity_from_text(html_content)
        if quantity_from_html != "NA":
            product["quantity"] = quantity_from_html

    # Step 9: If pack_format still NA after LLM, try title/source/link text as fallback.
    if _needs_pack_detection(product):
        pack_from_text = _pack_format_from_text(
            product.get("product_name", ""),
            source_url,
            product.get("link", ""),
            product.get("image_link", ""),
        )
        if pack_from_text == "NA":
            pack_from_text = _pack_format_from_text(html_content)
        if pack_from_text != "NA":
            product["pack_format"] = pack_from_text
            print(f"[TEXT] Pack format '{pack_from_text}' from title/source/link: {product.get('product_name', '')}")

    product["availability"] = _resolve_availability(product, html_content=html_content)

    return product


def _apply_image_pack_formats(products: list[dict]) -> list[dict]:
    """
    Final fallback: detect pack format from images in parallel
    when text evidence is missing or the current value is unsupported by title/link.
    """
    needs_detection = [
        (i, p) for i, p in enumerate(products)
        if (
            _needs_pack_detection(p)
            or not _pack_format_has_text_support(p)
        )
        and p.get("image_link", "NA") not in ("NA", "data not available", "")
    ]

    if not needs_detection:
        return products

    print(f"[IMAGE] Detecting pack format for {len(needs_detection)} products in parallel...")

    # Deduplicate by image URL — but keep name hint from first occurrence
    url_to_hint: dict = {}
    for _, p in needs_detection:
        url = p.get("image_link", "")
        if url not in url_to_hint:
            # Use link slug as hint — has can/bottle/btl info sometimes
            hint = p.get("link", "") or p.get("brand", "")
            url_to_hint[url] = hint

    url_to_format: dict = {}
    with ThreadPoolExecutor(max_workers=IMAGE_DETECTION_WORKERS) as executor:
        future_to_url = {
            executor.submit(
                _detect_pack_format_from_image,
                url,
                url_to_hint.get(url, "")
            ): url
            for url in url_to_hint
            if url not in _image_pack_format_cache
        }

        # Add cached results
        for url in url_to_hint:
            if url in _image_pack_format_cache:
                url_to_format[url] = _image_pack_format_cache[url]

        # Collect parallel results
        for future in as_completed(future_to_url):
            url = future_to_url[future]
            try:
                url_to_format[url] = future.result()
            except Exception as e:
                print(f"[IMAGE] Failed for {url}: {e}")
                url_to_format[url] = "NA"

    # Apply results back to products
    for i, product in needs_detection:
        image_url = product.get("image_link", "")
        image_pack_format = url_to_format.get(image_url, "NA")
        text_pack_format = _pack_format_from_text(
            product.get("product_name", ""),
            product.get("link", ""),
            product.get("image_link", ""),
        )

        if text_pack_format != "NA":
            products[i]["pack_format"] = text_pack_format
        elif image_pack_format != "NA":
            products[i]["pack_format"] = image_pack_format

    return products


# ─── MAIN ENTRY ───────────────────────────────────────────────────────────────

def parse_html(html_content: str, input_type: str = "html", source_url: str = "") -> list[dict]:
    results = chain.invoke({
        "html_content": html_content,
        "input_type": input_type,
        "brand_list": _BRAND_LIST_STR,
        "format_instructions": parser.get_format_instructions(),
    })

    if isinstance(results, dict):
        results = [results]

    processed = []
    for product in results:
        try:
            if _is_draught(product):
                print(f"[SKIP] Draught: {product.get('link', 'unknown')}")
                continue
            if _is_non_alcoholic(product, source_url=source_url):
                print(f"[SKIP] Non-alcoholic: {product.get('link', product.get('product_name', 'unknown'))}")
                continue
            if _is_out_of_scope_product(product, source_url=source_url):
                print(f"[SKIP] Out of scope: {product.get('link', product.get('product_name', 'unknown'))}")
                continue
            processed.append(_process_product(
                product,
                input_type=input_type,
                html_content=html_content,
                source_url=source_url,
            ))
        except Exception as e:
            print(f"[WARN] Skipping product: {e}")
            continue

    processed = _apply_image_pack_formats(processed)

    return processed


def parse_html_code(html_content: str, input_type: str = "html", source_url: str = "") -> list[dict]:
    return parse_html(html_content, input_type=input_type, source_url=source_url)
