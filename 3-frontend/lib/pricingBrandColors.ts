const BRAND_COLORS: Record<string, string> = {
  heineken: "#16a34a",
  amstel: "#dc2626",
  "birra moretti": "#7f1d1d",
  tiger: "#2563eb",
  corona: "#facc15",
  carlsberg: "#6b7280",
  stella: "#111827",
  peroni: "#7c3aed",
  kingfisher: "#1e3a8a",
  "red horse": "#991b1b",
  haywards: "#374151",
};

const FALLBACK_COLORS = [
  "#06b6d4",
  "#f97316",
  "#8b5cf6",
  "#ec4899",
  "#14b8a6",
  "#64748b",
];

function normalizeBrandName(value: string) {
  return value
    .split("·")[0]
    .trim()
    .toLowerCase()
    .replace(/\s+/g, " ");
}

export function getPricingBrandColor(brand: string, fallbackIndex = 0) {
  return (
    BRAND_COLORS[normalizeBrandName(brand)] ??
    FALLBACK_COLORS[fallbackIndex % FALLBACK_COLORS.length]
  );
}

export function getPricingBrandLabel(value: string) {
  return value.split("·")[0].trim();
}
