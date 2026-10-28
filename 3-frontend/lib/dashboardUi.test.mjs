import test from "node:test";
import assert from "node:assert/strict";
import { countActiveFilters } from "./dashboardUi.ts";

test("counts meaningful filter values and ignores empty selections", () => {
  assert.equal(countActiveFilters({ search: "", selected: "", startDate: "", endDate: "" }), 0);
  assert.equal(countActiveFilters({ search: "coffee", selected: "", startDate: "", endDate: "" }), 1);
  assert.equal(countActiveFilters({ search: "coffee", selected: "sa", startDate: "2026-01-01", endDate: "2026-01-31" }), 4);
  assert.equal(countActiveFilters({ search: "   ", selected: null, startDate: undefined, endDate: [] }), 0);
});
