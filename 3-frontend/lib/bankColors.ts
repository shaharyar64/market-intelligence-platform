export const BANK_COLORS: Record<string, string> = {
  "al rajhi bank": "#0067B1",
  "alinma bank": "#00A6A6",
  gib: "#38A169",
  "gulf international bank": "#38A169",
  "stc bank": "#5B2C83",
  bsf: "#8C564B",
  "banque saudi fransi": "#8C564B",
  snb: "#006B3C",
  "saudi national bank": "#006B3C",
  "riyad bank": "#264653",
  anb: "#D62828",
  "arab national bank": "#D62828",
  "bank albilad": "#C2185B",
  saib: "#D4A017",
  "saudi investment bank": "#D4A017",
  "bank aljazira": "#3FA7D6",
  "bank al jazira": "#3FA7D6",
  sab: "#7A284B",
  "saudi awwal bank": "#7A284B",
  "d360 bank": "#F36C21",
  "vision bank": "#7CB518",
};

export const FALLBACK_COLORS = [
  "#2563eb",
  "#06b6d4",
  "#10b981",
  "#84cc16",
  "#f59e0b",
  "#f97316",
  "#ef4444",
  "#ec4899",
  "#8b5cf6",
  "#6366f1",
  "#14b8a6",
  "#64748b",
];

export function getBankColor(name: string, fallbackIndex = 0): string {
  const normalized = name.trim().toLowerCase().replace(/[_-]+/g, " ").replace(/\s+/g, " ");
  const match = BANK_COLORS[normalized];
  if (match) return match;

  return FALLBACK_COLORS[fallbackIndex % FALLBACK_COLORS.length];
}

/** Picks black or white text for legibility against a solid hex fill (WCAG relative luminance). */
export function getContrastText(hex: string): string {
  const clean = hex.replace("#", "");
  const r = parseInt(clean.slice(0, 2), 16) / 255;
  const g = parseInt(clean.slice(2, 4), 16) / 255;
  const b = parseInt(clean.slice(4, 6), 16) / 255;
  const toLinear = (channel: number) =>
    channel <= 0.03928 ? channel / 12.92 : Math.pow((channel + 0.055) / 1.055, 2.4);
  const luminance = 0.2126 * toLinear(r) + 0.7152 * toLinear(g) + 0.0722 * toLinear(b);

  return luminance > 0.45 ? "#111827" : "#ffffff";
}
