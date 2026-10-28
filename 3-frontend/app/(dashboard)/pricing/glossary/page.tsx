"use client";

import DashboardTopbar from "@/components/layout/DashboardTopbar";

/* =========================
   METRIC DEFINITIONS DATA
========================= */

const SECTIONS: {
  title: string;
  accent: string;
  headerBg: string;
  rows: { metric: string; definition: string }[];
}[] = [
  {
    title: "Pricing (Product Listings - Level Analysis)",
    accent: "#06b6d4",
    headerBg: "#164e63",
    rows: [
      { metric: "Regular Price", definition: "Standard non-promotional SKU price." },
      { metric: "Promo Price", definition: "Promotional/discounted SKU price." },
      { metric: "Promo %", definition: "Percentage discount between regular and promotional price." },
      { metric: "Difference vs PP", definition: "Change versus Previous Period." },
      { metric: "Aggregated Regional Metrics", definition: "Average of retailer metrics within Dubai, Abu Dhabi, Northern Emirates, and Bahrain. Retailers operating across multiple emirates contribute to each relevant emirate. Calculated as: Sum of retailer metrics ÷ number of relevant retailers." },
    ],
  },
  {
    title: "Digital Shelf (Product Listings - Level Analysis)",
    accent: "#6366f1",
    headerBg: "#1e1b4b",
    rows: [
      { metric: "% Top 10 / % First Page", definition: "Visibility share within retailer Top 10 and First Page listings." },
      { metric: "Difference vs PP", definition: "Change versus Previous Period." },
      { metric: "Aggregated Visibility Metrics", definition: "Total no. of times YES ÷ Total retailers in Dubai." },
      { metric: "Brand Total # Product Listings", definition: "Total no. of Product Listings with YES." },
      { metric: "Brand Share in Top 10", definition: "Sum of Product Listings with YES ÷ (10 × No. of retailers in Dubai)." },
    ],
  },
];

/* =========================
   RETAILERS DATA
========================= */

interface Retailer {
  company: string;
  coverage?: string;
}

const UAE_RETAILERS: Retailer[] = [
  { company: "MMI Home Delivery",       coverage: "Dubai, Other Emirates" },
  { company: "African Eastern Online",  coverage: "Dubai, Abu Dhabi, Other Emirates" },
  { company: "CityDrinks",              coverage: "Abu Dhabi" },
  { company: "Home High Spirits",       coverage: "Abu Dhabi" },
  { company: "Centaurus International", coverage: "Abu Dhabi" },
  { company: "GMP",                     coverage: "Abu Dhabi" },
  { company: "Super Cellar",            coverage: "Other Emirates" },
  { company: "JMK Cellar",              coverage: "Other Emirates" },
  { company: "Royal Spirit",            coverage: "Abu Dhabi" },
  { company: "Windmill GT",             coverage: "Abu Dhabi" },
  { company: "The Original Barracuda",  coverage: "Other Emirates" },
  { company: "Unisat",                  coverage: "Other Emirates" },
  { company: "Spinneys",                coverage: "Abu Dhabi" },
  { company: "The Bottle Store",        coverage: "Abu Dhabi" },
  { company: "Dubai Duty Free",         coverage: "Dubai" },
];

const BAHRAIN_RETAILERS: Retailer[] = [
  { company: "BMMI Shops",               coverage: "Bahrain" },
  { company: "Africa Eastern",           coverage: "Bahrain" },
  { company: "Gulf Brands International",coverage: "Bahrain" },
  { company: "NHSC Shop",               coverage: "Bahrain" },
  { company: "Bahrain Duty Free",        coverage: "Bahrain" },
];

/* =========================
   COMPONENTS
========================= */

function SectionTable({
  title,
  accent,
  headerBg,
  rows,
}: {
  title: string;
  accent: string;
  headerBg: string;
  rows: { metric: string; definition: string }[];
}) {
  return (
    <div className="rounded-2xl overflow-hidden border border-[var(--card-bd)] shadow-md">
      <div className="px-5 py-3 flex items-center gap-3" style={{ background: headerBg }}>
        <span className="inline-block w-2 h-2 rounded-full flex-shrink-0" style={{ background: accent }} />
        <span className="text-white font-bold text-sm tracking-wide">{title}</span>
      </div>
      <table className="w-full border-collapse">
        <thead>
          <tr style={{ background: "var(--card-bg-2)" }}>
            <th
              className="text-left px-5 py-3 text-xs font-semibold uppercase tracking-widest"
              style={{ color: accent, width: "30%", borderBottom: `2px solid ${accent}33` }}
            >
              Metric
            </th>
            <th
              className="text-left px-5 py-3 text-xs font-semibold uppercase tracking-widest"
              style={{ color: "var(--muted-tx)", borderBottom: `2px solid ${accent}33` }}
            >
              Definition
            </th>
          </tr>
        </thead>
        <tbody>
          {rows.map((row, i) => (
            <tr
              key={i}
              style={{
                background: i % 2 === 0 ? "var(--card-bg)" : "var(--card-bg-2)",
                borderBottom: "1px solid var(--card-bd)",
              }}
            >
              <td
                className="px-5 py-3.5 text-sm font-semibold"
                style={{ color: "var(--title-tx)", width: "30%", borderRight: `1px solid ${accent}22` }}
              >
                {row.metric}
              </td>
              <td className="px-5 py-3.5 text-sm" style={{ color: "var(--body-tx)", lineHeight: 1.6 }}>
                {row.definition}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}


/* =========================
   PAGE
========================= */

export default function GlossaryPage() {
  return (
    <div className="w-full bg-transparent" style={{ minHeight: "100%" }}>
      <DashboardTopbar title="Glossary" />

      <div className="p-8 space-y-10">

        {/* Retailers Reference */}
        <section>
          <h2 className="text-lg font-bold mb-1" style={{ color: "var(--title-tx)" }}>
            Retailers
          </h2>
          <p className="text-sm mb-4" style={{ color: "var(--muted-tx)" }}>
            Retailers tracked across UAE and Bahrain markets with their regional coverage.
          </p>

          <div className="rounded-2xl overflow-hidden border border-[var(--card-bd)] shadow-md">
            <table className="w-full border-collapse">
              <thead>
                <tr style={{ background: "#1e3a5f" }}>
                  <th className="text-left px-5 py-3 text-xs font-semibold uppercase tracking-widest text-white" style={{ width: "40%" }}>
                    Company
                  </th>
                  <th className="text-left px-5 py-3 text-xs font-semibold uppercase tracking-widest text-white">
                    Markets
                  </th>
                </tr>
              </thead>
              <tbody>
                {/* UAE retailers */}
                {UAE_RETAILERS.map((row, i) => (
                  <tr
                    key={row.company}
                    style={{
                      background: i % 2 === 0 ? "var(--card-bg)" : "var(--card-bg-2)",
                      borderBottom: "1px solid var(--card-bd)",
                    }}
                  >
                    <td className="px-5 py-3.5 text-sm font-semibold" style={{ color: "var(--title-tx)", borderRight: "1px solid var(--card-bd)" }}>
                      {row.company}
                    </td>
                    <td className="px-5 py-3.5 text-sm" style={{ color: "var(--body-tx)" }}>
                      {row.coverage ?? <span style={{ color: "#d1d5db" }}>–</span>}
                    </td>
                  </tr>
                ))}

                {/* Bahrain retailers */}
                {BAHRAIN_RETAILERS.map((row, i) => (
                  <tr
                    key={row.company}
                    style={{
                      background: i % 2 === 0 ? "var(--card-bg)" : "var(--card-bg-2)",
                      borderBottom: "1px solid var(--card-bd)",
                    }}
                  >
                    <td className="px-5 py-3.5 text-sm font-semibold" style={{ color: "var(--title-tx)", borderRight: "1px solid var(--card-bd)" }}>
                      {row.company}
                    </td>
                    <td className="px-5 py-3.5 text-sm" style={{ color: "var(--body-tx)" }}>
                      {row.coverage ?? <span style={{ color: "#d1d5db" }}>–</span>}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </section>

        {/* Metric Definitions */}
        <section>
          <h2 className="text-lg font-bold mb-4" style={{ color: "var(--title-tx)" }}>
            Metric Definitions
          </h2>
          <div className="space-y-6">
            {SECTIONS.map((s) => (
              <SectionTable key={s.title} {...s} />
            ))}
          </div>
        </section>

      </div>
    </div>
  );
}
