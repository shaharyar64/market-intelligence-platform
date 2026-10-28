export function countActiveFilters(filters: Record<string, unknown>): number {
  return Object.values(filters).filter((value) => {
    if (typeof value === "string") return value.trim().length > 0;
    if (Array.isArray(value)) return value.length > 0;
    return value !== null && value !== undefined;
  }).length;
}
