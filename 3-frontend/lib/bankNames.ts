// Some data sources (e.g. AI Score, Social) report full/legacy legal bank
// names instead of the short codes used everywhere else (top-digital-health,
// Reviews, filters/banks). This keeps one canonical mapping so any page that
// needs to join rows across sources by bank name resolves consistently.
const BANK_NAME_ALIASES: Record<string, string> = {
  arabnationalbank: "anb",
  banquesaudifransi: "bsf",
  saudiinvestmentbank: "saib",
  gulfinternationalbank: "gib",
  snbalahli: "snb",
  saudinationalbank: "snb",
  saudiawwalbank: "sab",
};

// Real-estate sources report the same developer with different trailing
// corporate suffixes depending on the table (e.g. social data says "Emaar",
// ai-score/search/reviews say "Emaar Properties"). Strip one trailing suffix
// so cross-source joins resolve without over-collapsing distinct names.
const CORPORATE_SUFFIXES = [
  "properties",
  "property",
  "developments",
  "development",
  "developers",
  "developer",
  "holdings",
  "holding",
  "realestate",
  "realty",
  "investments",
  "investment",
  "group",
  "llc",
];

function stripCorporateSuffix(key: string): string {
  for (const suffix of CORPORATE_SUFFIXES) {
    if (key.length > suffix.length && key.endsWith(suffix)) {
      return key.slice(0, key.length - suffix.length);
    }
  }
  return key;
}

export function normalizeBankKey(name: string): string {
  const key = name.trim().toLowerCase().replace(/[^a-z0-9]/g, "");
  const aliased = BANK_NAME_ALIASES[key] ?? key;
  return stripCorporateSuffix(aliased);
}
