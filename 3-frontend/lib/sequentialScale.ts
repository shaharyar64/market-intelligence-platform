const ACCENT_RGB = "37, 99, 235";
const MIN_ALPHA = 0.08;
const MAX_ALPHA = 0.95;
const WHITE_TEXT_THRESHOLD = 0.55;

function normalizedAlpha(score: number, max: number) {
  const ratio = max > 0 ? Math.min(Math.max(score / max, 0), 1) : 0;
  return MIN_ALPHA + ratio * (MAX_ALPHA - MIN_ALPHA);
}

/** Sequential single-hue cell fill for a 0..max magnitude heatmap, alpha-composited over the theme surface. */
export function sequentialCellColor(score: number, max: number): string {
  return `rgba(${ACCENT_RGB}, ${normalizedAlpha(score, max).toFixed(2)})`;
}

/** Text color that stays legible against sequentialCellColor at the same score/max. */
export function sequentialCellTextColor(score: number, max: number): string {
  return normalizedAlpha(score, max) >= WHITE_TEXT_THRESHOLD ? "#ffffff" : "var(--title-tx)";
}
