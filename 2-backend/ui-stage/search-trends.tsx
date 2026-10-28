"use client";

import { useState } from "react";
import dynamic from "next/dynamic";
import {
  CartesianGrid,
  Legend,
  Line,
  LineChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import {
  getSearchInterest,
  getSearchRegions,
  type SearchKeyword,
} from "@/lib/ceerCampaign";
import { searchInterestSeries } from "@/lib/ceerCampaignAnalysis";
import { useAsyncResource } from "@/lib/useAsyncResource";
import { axis, Chart, Load, Note, number, Panel, s, tooltip } from "./shared";

const CeerSearchMap = dynamic(() => import("@/components/maps/CeerSearchMap"), {
  ssr: false,
  loading: () => <div className={s.loading}>Loading regional map…</div>,
});

const searchColors = ["#087d79", "#5879bb", "#a65a88", "#b17a37", "#697582"];
const searchKeywords: SearchKeyword[] = ["ceer", "exobot"];
const trendDate = (date: string) =>
  new Date(`${date}T00:00:00Z`).toLocaleDateString("en", {
    day: "numeric",
    month: "short",
    timeZone: "UTC",
  });

export default function SearchTrendPanels() {
  const [searchKeyword, setSearchKeyword] = useState<SearchKeyword>("ceer");
  const searchInterest = useAsyncResource(
    (signal) => getSearchInterest(searchKeyword, signal),
    [searchKeyword],
  );
  const searchRegions = useAsyncResource(
    (signal) => getSearchRegions(searchKeyword, signal),
    [searchKeyword],
  );
  const searchLabel = searchKeyword.toUpperCase();

  return (
    <section className={s.section} aria-label="Google Trends search interest">
      <div className={s.searchTabs} role="tablist" aria-label="Search term">
        {searchKeywords.map((keyword) => (
          <button
            key={keyword}
            type="button"
            role="tab"
            aria-selected={searchKeyword === keyword}
            className={searchKeyword === keyword ? s.searchTabActive : s.searchTab}
            onClick={() => setSearchKeyword(keyword)}
          >
            {keyword.toUpperCase()}
          </button>
        ))}
      </div>

      <Panel
        title={`${searchLabel} search interest around the reveal`}
        description={`Google Trends interest for ${searchLabel}. This is external search demand, not social engagement.`}
      >
        <Load resource={searchInterest}>
          {(rows) => {
            const series = searchInterestSeries(rows);
            return (
              <>
                <Chart label="Google Trends search interest over time">
                  <ResponsiveContainer width="100%" height="100%">
                    <LineChart data={series.data} margin={{ left: 0, right: 8 }}>
                      <CartesianGrid vertical={false} stroke="var(--ceer-line)" strokeDasharray="3 4" />
                      <XAxis {...axis} dataKey="date" tickFormatter={trendDate} />
                      <YAxis {...axis} domain={[0, 100]} width={34} />
                      <Tooltip
                        contentStyle={tooltip}
                        labelFormatter={(label) => trendDate(String(label))}
                        formatter={(value) => number(Number(value))}
                      />
                      <Legend />
                      {series.keys.map((key, index) => (
                        <Line
                          key={key}
                          type="monotone"
                          dataKey={key}
                          name={key}
                          stroke={searchColors[index]}
                          strokeWidth={2}
                          dot={false}
                          connectNulls
                        />
                      ))}
                    </LineChart>
                  </ResponsiveContainer>
                </Chart>
                <Note>Google Trends values are indexed search interest, not search volume.</Note>
              </>
            );
          }}
        </Load>
      </Panel>

      <Panel
        title={`Where ${searchLabel} search interest is strongest`}
        description={`Latest Google Trends regional snapshot for ${searchLabel} across Saudi Arabia. Province fill colour shows relative interest.`}
      >
        <Load resource={searchRegions}>
          {(rows) => (
            <>
              <CeerSearchMap data={rows} />
              <Note>Hover a province for its score. Regional Trends scores are relative within the selected snapshot.</Note>
            </>
          )}
        </Load>
      </Panel>
    </section>
  );
}
