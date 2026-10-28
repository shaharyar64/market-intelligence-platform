import test from "node:test";
import assert from "node:assert/strict";
import { toStructuredMarkdown } from "./assistantResponse.ts";

test("converts backend line breaks and named sections into readable markdown", () => {
  assert.equal(
    toStructuredMarkdown("Section A: Market lead<br>Section C: - Strong reviews<br>- High visibility"),
    "## Summary\n\nMarket lead\n\n## Drivers & notes\n\n- Strong reviews\n- High visibility",
  );
});

test("splits inline ranked results into an ordered list without changing scores", () => {
  assert.equal(
    toStructuredMarkdown("Top banks: 1. Emirates NBD — 95.8 2. FAB — 94.0"),
    "### Top banks\n\n1. Emirates NBD — 95.8\n2. FAB — 94.0",
  );
});

test("repairs pipe tables that are missing a separator row and lifts the inline label", () => {
  assert.equal(
    toStructuredMarkdown("Component comparison: Metric | DIB | ENBD\nBrandIQ rank | 4th | 1st\nAI score | 70.00 | 97.16"),
    "### Component comparison\n\n| Metric | DIB | ENBD |\n| --- | ---: | ---: |\n| BrandIQ rank | 4th | 1st |\n| AI score | 70.00 | 97.16 |",
  );
});

test("leaves well-formed tables untouched", () => {
  const table = "| Metric | DIB |\n|---|---:|\n| AI score | 70.00 |";
  assert.equal(toStructuredMarkdown(table), table);
});

test("turns bullet characters into list items and label lines into headings", () => {
  assert.equal(
    toStructuredMarkdown("Key takeaways: • DIB leads ADIB. • DIB trails Emirates NBD.\n\n**What stands out**\n- Social is weak"),
    "### Key takeaways\n\n- DIB leads ADIB.\n- DIB trails Emirates NBD.\n\n### What stands out\n\n- Social is weak",
  );
});

test("keeps source notes as plain paragraphs", () => {
  assert.equal(toStructuredMarkdown("Source: BrandIQ snapshot."), "Source: BrandIQ snapshot.");
});
