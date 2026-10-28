"use client";

import ExportExcelButton from "@/components/ui/ExportExcelButton";
import { sequentialCellColor, sequentialCellTextColor } from "@/lib/sequentialScale";
import { formatAiScoreCategoryLabel } from "@/lib/bankBrandHealth";

type HeatmapItem = {
  bank?: string | null;
  developer?: string | null;
  score: number;
};

function itemName(item: HeatmapItem): string {
  return (item.developer ?? item.bank ?? "").toString().trim();
}

type BankCategoryHeatmapProps = {
  title: string;
  description: string;
  data: Record<string, HeatmapItem[]>;
  excludeKeys?: string[];
  scaleMax?: number;
  loading?: boolean;
  filenamePrefix: string;
  rowLabel?: string;
};

function formatExportLabel(value: string) {
  return value
    .trim()
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, "_")
    .replace(/^_+|_+$/g, "");
}

export default function BankCategoryHeatmap({
  title,
  description,
  data,
  excludeKeys = ["overall"],
  scaleMax = 10,
  loading = false,
  filenamePrefix,
  rowLabel = "Bank",
}: BankCategoryHeatmapProps) {
  const categories = Object.keys(data).filter((key) => !excludeKeys.includes(key));
  const banks = Array.from(
    new Set(
      categories
        .flatMap((category) => (data[category] ?? []).map((item) => itemName(item)))
        .filter(Boolean)
    )
  );

  const scoreMap = new Map<string, number>();
  categories.forEach((category) => {
    (data[category] ?? []).forEach((item) => {
      const name = itemName(item);
      if (!name) return;
      scoreMap.set(`${name}::${category}`, item.score);
    });
  });

  const exportRowKey = rowLabel.toLowerCase();
  const exportRows = banks.flatMap((bank) =>
    categories.map((category) => ({
      [exportRowKey]: bank,
      category: formatAiScoreCategoryLabel(category),
      score: scoreMap.get(`${bank}::${category}`) ?? 0,
    }))
  );
  return (
    <div className="mt-6 overflow-hidden rounded-2xl border border-[var(--card-bd)] bg-[var(--card-bg)] shadow-sm">
      <div className="flex flex-col gap-4 px-5 pt-5 lg:flex-row lg:items-start lg:justify-between">
        <div>
          <h3 className="text-sm font-medium text-[var(--muted-tx)]">{title}</h3>
          <p className="mt-1 text-sm text-[var(--muted-tx)]">{description}</p>
        </div>
        <ExportExcelButton rows={exportRows} filename={formatExportLabel(filenamePrefix)} sheetName={title} disabled={loading} />
      </div>

      {loading ? (
        <div className="m-5 h-[240px] animate-pulse rounded-2xl bg-[var(--card-bg-2)]" />
      ) : banks.length === 0 || categories.length === 0 ? (
        <div className="m-5 flex h-[160px] items-center justify-center rounded-2xl border border-dashed border-[var(--card-bd)] text-sm text-[var(--muted-tx)]">
          No data available
        </div>
      ) : (
        <>
          <div className="flex justify-end px-5 pb-3 pt-4">
            <div className="flex items-end gap-1.5 text-[10px] font-medium text-[var(--muted-tx)]">
              <div className="mr-1 pb-0.5">Low</div>
              {[0.12, 0.32, 0.55, 0.76, 0.95].map((alpha, index) => (
                <div key={alpha} className="text-center">
                  <div className="h-3 w-12 rounded-sm" style={{ background: `rgba(37,99,235,${alpha})` }} />
                  {index === 0 ? <span className="mt-1 block">0</span> : index === 4 ? <span className="mt-1 block">{scaleMax}</span> : null}
                </div>
              ))}
              <div className="ml-1 pb-0.5">High</div>
            </div>
          </div>
          <div className="px-5 pb-5 pt-2">
            <div
              className="grid w-full gap-1 text-xs sm:gap-1.5"
              style={{ gridTemplateColumns: `minmax(112px, 168px) repeat(${categories.length}, minmax(0, 1fr))` }}
            >
            <div className="flex min-h-14 items-end px-1 pb-2 text-[9px] font-semibold uppercase tracking-[0.12em] text-[var(--muted-tx)] sm:text-[10px]">{rowLabel}</div>
            {categories.map((category) => (
              <div
                key={category}
                title={formatAiScoreCategoryLabel(category)}
                className="flex min-h-14 min-w-0 items-end justify-center break-words px-0.5 pb-2 text-center text-[8px] font-medium leading-3 text-[var(--muted-tx)] sm:px-1 sm:text-[10px] sm:leading-4"
              >
                {formatAiScoreCategoryLabel(category)}
              </div>
            ))}

            {banks.map((bank) => (
              <div key={bank} className="contents">
                <div className="flex min-h-10 min-w-0 items-center break-words px-1 py-1.5 text-[10px] font-medium leading-4 text-[var(--title-tx)] sm:min-h-11 sm:text-xs sm:leading-5">
                  {bank}
                </div>
                {categories.map((category) => {
                  const score = scoreMap.get(`${bank}::${category}`);

                  return (
                    <div
                      key={`${bank}-${category}`}
                      className="group relative flex min-h-10 min-w-0 items-center justify-center rounded-md border border-white/40 px-0.5 text-[10px] font-semibold transition duration-150 hover:z-[5] hover:-translate-y-0.5 hover:scale-[1.03] hover:shadow-md hover:ring-2 hover:ring-blue-500/25 sm:min-h-11 sm:text-sm"
                      style={{
                        background: score === undefined ? "var(--card-bg-2)" : sequentialCellColor(score, scaleMax),
                        color: score === undefined ? "var(--muted-tx)" : sequentialCellTextColor(score, scaleMax),
                      }}
                      title={`${bank} • ${formatAiScoreCategoryLabel(category)}: ${score ?? "No data"}`}
                    >
                      {score ?? "–"}
                    </div>
                  );
                })}
              </div>
            ))}
            </div>
          </div>
        </>
      )}
    </div>
  );
}
