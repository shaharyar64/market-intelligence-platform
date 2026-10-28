const SECTION_TITLES: Record<string, string> = {
  A: "Summary",
  B: "Insights",
  C: "Drivers & notes",
  D: "Recommendations",
};

const NUMERIC_CELL = /^[-+]?[\d.,]+(?:%|\/\d+|st|nd|rd|th|×|x)?$/;

const TABLE_SEPARATOR = /^\s*\|?\s*:?-{2,}:?\s*(\|\s*:?-{2,}:?\s*)*\|?\s*$/;

function tableCells(line: string): string[] {
  return line.trim().replace(/^\|/, "").replace(/\|$/, "").split("|").map((cell) => cell.trim());
}

/** Turns runs of pipe-delimited lines into GFM tables, adding the separator row models often omit. */
function repairTables(markdown: string): string {
  const lines = markdown.split("\n");
  const output: string[] = [];

  for (let i = 0; i < lines.length; ) {
    const start = i;
    while (i < lines.length && (lines[i].match(/\|/g)?.length ?? 0) >= 2) i++;
    if (i - start < 2) {
      output.push(lines[start]);
      i = start + 1;
      continue;
    }

    const block = lines.slice(start, i);
    if (TABLE_SEPARATOR.test(block[1])) {
      output.push("", ...block, "");
      continue;
    }

    // "Component comparison: Metric | A | B" → label line, then the header row.
    const header = tableCells(block[0]);
    const label = header[0].match(/^(.+?):\s+(.+)$/);
    if (label) {
      output.push("", `${label[1]}:`);
      header[0] = label[2];
    }
    const rows = [header, ...block.slice(1).map(tableCells)];
    output.push(
      "",
      `| ${rows[0].join(" | ")} |`,
      `| ${rows[0].map((_, col) => (col > 0 && rows.slice(1).every((cells) => NUMERIC_CELL.test(cells[col] ?? "")) ? "---:" : "---")).join(" | ")} |`,
      ...rows.slice(1).map((cells) => `| ${cells.join(" | ")} |`),
      "",
    );
  }

  return output.join("\n");
}

/** Converts the legacy assistant protocol and loosely formatted model output into readable Markdown. */
export function toStructuredMarkdown(response: string): string {
  const withLineBreaks = response
    .replace(/<br\s*\/?>/gi, "\n")
    .replace(/\r\n?/g, "\n")
    .trim();

  const withHeadings = withLineBreaks.replace(
    /(?:^|\n)\s*Section\s+([A-D])\s*:\s*/gi,
    (_match, section: string) => `\n\n## ${SECTION_TITLES[section.toUpperCase()]}\n\n`,
  );

  const withBullets = withHeadings
    .replace(/(^|\n)[ \t]*[•●▪][ \t]+/g, "$1- ")
    .replace(/[ \t]+[•●▪][ \t]+/g, "\n- ")
    .replace(/([^\n])\s+(\d+)\.\s+(?=[A-Z])/g, "$1\n$2. ");

  // A short line that is entirely bold, or ends with a colon, labels what follows it.
  const withLabels = repairTables(withBullets).replace(
    /^(?:\*\*([^*\n|]{1,60}?):?\*\*|([A-Z][^*\n|:.]{1,48}):)[ \t]*$/gm,
    (_match, bold?: string, plain?: string) => `\n### ${(bold ?? plain ?? "").trim()}\n`,
  );

  return withLabels.replace(/\n{3,}/g, "\n\n").replace(/^\s+|\s+$/g, "");
}
