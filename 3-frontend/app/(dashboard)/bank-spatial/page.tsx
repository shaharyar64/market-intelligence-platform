"use client";

import { useEffect, useState } from "react";
import DashboardTopbar from "@/components/layout/DashboardTopbar";
import { Blocks, Users, Star, Landmark } from "lucide-react";
import GlassStatCard from "@/components/ui/StatCard";
import PieChartCard from "@/components/analytics/charts/PieChartCard";
import BarChartCard from "@/components/analytics/charts/BarChartCard";
import AreaChartCard from "@/components/analytics/charts/AreaChartCard";
import { getBankColor } from "@/lib/bankColors";
import {
  getBankSpatialKPIs,
  getBankSpatialCategories,
  getBankSpatialRatingDistribution,
  getBankSpatialBanksMarket,
  getFilters,
} from "@/lib/bankSpatial";
import FilterSelect from "@/components/filters/FilterSelect";

interface FiltersResponse {
  clusters: string[];
  sub_clusters: string[];
  zones: string[];
  countries: string[];
  categories: string[];
}

export default function BankingSpatialPage() {
  /* =========================
     STATE
  ========================== */

  const [kpis, setKpis] = useState<any>(null);
  const [categories, setCategories] = useState<any>(null);
  const [ratingDistribution, setRatingDistribution] = useState<any>(null);
  const [banksMarket, setBanksMarket] = useState<any>(null);
  const [loading, setLoading] = useState(true);
  const [filters, setFilters] = useState<FiltersResponse | null>(null);

  const [selectedFilters, setSelectedFilters] = useState({
    cluster: "",
    sub_cluster: "",
    zone: "",
    country: "",
    category: "",
  });

  type HeatmapData = Record<string, number[]>;

  /* =========================
     POPULAR TIMINGS (FILTERED BY CLUSTER)
  ========================== */

  const popularTimingsData: any = {
    "Historic Core": {
      weekday: [
        { time: "6AM", value: 40 },
        { time: "7AM", value: 45 },
        { time: "8AM", value: 85 },
        { time: "9AM", value: 90 },
        { time: "10AM", value: 92 },
        { time: "11AM", value: 50 },
        { time: "12PM", value: 65 },
        { time: "1PM", value: 78 },
        { time: "2PM", value: 60 },
        { time: "3PM", value: 95 },
        { time: "4PM", value: 88 },
        { time: "5PM", value: 80 },
        { time: "6PM", value: 60 },
        { time: "7PM", value: 58 },
        { time: "8PM", value: 55 },
        { time: "9PM", value: 70 },
        { time: "10PM", value: 68 },
      ],
      weekend: [
        { time: "6AM", value: 35 },
        { time: "7AM", value: 50 },
        { time: "8AM", value: 80 },
        { time: "9AM", value: 85 },
        { time: "10AM", value: 88 },
        { time: "11AM", value: 60 },
        { time: "12PM", value: 75 },
        { time: "1PM", value: 82 },
        { time: "2PM", value: 70 },
        { time: "3PM", value: 98 },
        { time: "4PM", value: 90 },
        { time: "5PM", value: 85 },
        { time: "6PM", value: 65 },
        { time: "7PM", value: 63 },
        { time: "8PM", value: 60 },
        { time: "9PM", value: 75 },
        { time: "10PM", value: 72 },
      ],
    },

    "Inner Suburban East": {
      weekday: [
        { time: "6AM", value: 30 },
        { time: "7AM", value: 35 },
        { time: "8AM", value: 70 },
        { time: "9AM", value: 75 },
        { time: "10AM", value: 78 },
        { time: "11AM", value: 40 },
        { time: "12PM", value: 55 },
        { time: "1PM", value: 65 },
        { time: "2PM", value: 50 },
        { time: "3PM", value: 80 },
        { time: "4PM", value: 75 },
        { time: "5PM", value: 70 },
        { time: "6PM", value: 45 },
        { time: "7PM", value: 45 },
        { time: "8PM", value: 43 },
        { time: "9PM", value: 60 },
        { time: "10PM", value: 58 },
      ],
      weekend: [
        { time: "6AM", value: 28 },
        { time: "7AM", value: 38 },
        { time: "8AM", value: 68 },
        { time: "9AM", value: 72 },
        { time: "10AM", value: 75 },
        { time: "11AM", value: 48 },
        { time: "12PM", value: 62 },
        { time: "1PM", value: 70 },
        { time: "2PM", value: 58 },
        { time: "3PM", value: 85 },
        { time: "4PM", value: 80 },
        { time: "5PM", value: 75 },
        { time: "6PM", value: 55 },
        { time: "7PM", value: 53 },
        { time: "8PM", value: 50 },
        { time: "9PM", value: 65 },
        { time: "10PM", value: 63 },
      ],
    },
  };

  const [footfallView, setFootfallView] =
    useState<"weekday" | "weekend">("weekday");

  const activeCluster =
    selectedFilters.cluster || "Historic Core";

  const activeFootfallData =
    popularTimingsData[activeCluster]?.[footfallView] ||
    popularTimingsData["Historic Core"][footfallView];

  /* =========================
     HEATMAP (FILTERED BY ZONE)
  ========================== */

  const baseHeatmap: HeatmapData = {
    Sun: [27, 21, 79, 75, 71, 37, 54, 66, 39, 73, 81, 69, 55, 49, 43, 57, 51],
    Mon: [19, 25, 75, 83, 71, 29, 58, 62, 47, 73, 73, 73, 51, 57, 43, 49, 55],
    Tue: [31, 29, 71, 71, 71, 41, 62, 58, 35, 73, 85, 77, 47, 45, 43, 61, 59],
    Wed: [23, 33, 67, 79, 71, 33, 66, 54, 43, 73, 77, 81, 43, 53, 43, 53, 63],
    Thu: [15, 17, 63, 67, 71, 25, 50, 50, 31, 73, 69, 65, 39, 41, 43, 45, 47],
    Fri: [17, 14, 31, 31, 24, 45, 46, 69, 65, 50, 84, 72, 80, 68, 34, 47, 40],
    Sat: [9, 18, 27, 39, 24, 37, 50, 65, 73, 50, 76, 76, 76, 76, 34, 39, 44],
  };

  const heatmapByZone: Record<string, HeatmapData> = {
    "Al Barsha First": baseHeatmap,
    "Al Karama": baseHeatmap,
    "Al Muraqqabat": baseHeatmap,
  };

  const activeHeatmap =
    heatmapByZone[selectedFilters.zone] || baseHeatmap;

  const hours = [
    "6AM","7AM","8AM","9AM","10AM","11AM",
    "12PM","1PM","2PM","3PM","4PM","5PM",
    "6PM","7PM","8PM","9PM","10PM"
  ];

  const getHeatColor = (value: number) => {
    if (value < 30) return "bg-red-600";
    if (value < 60) return "bg-yellow-500";
    return "bg-emerald-500";
  };

  /* =========================
     API CALLS
  ========================== */

  useEffect(() => {
    getFilters().then(setFilters);
  }, []);

  useEffect(() => {
    setLoading(true);
    getBankSpatialKPIs(selectedFilters)
      .then(setKpis)
      .finally(() => setLoading(false));
  }, [selectedFilters]);

  useEffect(() => {
    getBankSpatialCategories(selectedFilters)
      .then(setCategories);
  }, [selectedFilters]);

  useEffect(() => {
    getBankSpatialRatingDistribution(selectedFilters)
      .then(setRatingDistribution);
  }, [selectedFilters]);

  useEffect(() => {
    getBankSpatialBanksMarket(selectedFilters)
      .then(setBanksMarket);
  }, [selectedFilters]);

  const handleChange = (key: string, value: string) => {
    setSelectedFilters((prev) => ({
      ...prev,
      [key]: value,
    }));
  };

  const resetFilters = () => {
    setSelectedFilters({
      cluster: "",
      sub_cluster: "",
      zone: "",
      country: "",
      category: "",
    });
  };

  const buildOptions = (items: string[], label: string) => [
    { label, value: "" },
    ...items.map((item) => ({ label: item, value: item })),
  ];

  /* =========================
     UI
  ========================== */

  return (
    <div className="min-h-screen bg-transparent">
      <DashboardTopbar
        title="Banking Spatial Intelligence"
      />

      <div className="p-8">

        {/* FILTER PANEL */}
        <div className="rounded-2xl bg-[var(--card-bg)] p-6 shadow-xl border border-[var(--card-bd)] mb-8">
          {filters && (
            <div className="grid grid-cols-1 md:grid-cols-5 gap-4">
              <FilterSelect
                label="Cluster"
                value={selectedFilters.cluster}
                onChange={(val) => handleChange("cluster", val)}
                options={buildOptions(filters.clusters, "All Clusters")}
              />
              <FilterSelect
                label="Sub Cluster"
                value={selectedFilters.sub_cluster}
                onChange={(val) => handleChange("sub_cluster", val)}
                options={buildOptions(filters.sub_clusters, "All Sub Clusters")}
              />
              <FilterSelect
                label="Zone"
                value={selectedFilters.zone}
                onChange={(val) => handleChange("zone", val)}
                options={buildOptions(filters.zones, "All Zones")}
              />
              <FilterSelect
                label="Country"
                value={selectedFilters.country}
                onChange={(val) => handleChange("country", val)}
                options={buildOptions(filters.countries, "All Countries")}
              />
              <FilterSelect
                label="Category"
                value={selectedFilters.category}
                onChange={(val) => handleChange("category", val)}
                options={buildOptions(filters.categories, "All Categories")}
              />
            </div>
          )}

          <div className="flex justify-end mt-6">
            <button
              onClick={resetFilters}
              className="px-5 py-2 text-sm bg-white text-slate-900 rounded-xl hover:bg-slate-200 transition"
            >
              Reset Filters
            </button>
          </div>
        </div>

        {/* KPIs */}
        <div className="rounded-2xl bg-[var(--card-bg-2)] border border-[var(--card-bd)] p-6 shadow-lg">
          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-6">
            <GlassStatCard
              title="Total Categories"
              value={kpis?.total_categories}
              loading={loading}
              icon={<Blocks size={18} />}
              gradient="from-emerald-500 to-teal-500"
            />
            <GlassStatCard
              title="Total Reviews"
              value={kpis?.total_reviews}
              loading={loading}
              icon={<Star size={18} />}
              gradient="from-amber-500 to-orange-500"
            />
            <GlassStatCard
              title="Total Population"
              value={kpis?.total_population}
              loading={loading}
              icon={<Users size={18} />}
              gradient="from-indigo-500 to-purple-500"
            />
            <GlassStatCard
              title="Average Rating"
              value={kpis?.average_rating}
              loading={loading}
              icon={<Star size={18} />}
              gradient="from-pink-500 to-rose-500"
            />

            <GlassStatCard
              title="Average Number Per Zone"
              value="16"
              loading={loading}
              icon={<Star size={18} />}
              gradient="from-blue-500 to-rose-500"
            />

            <GlassStatCard
              title="Banking Coverage Index"
              value="1.2"
              loading={loading}
              icon={<Landmark size={18} />}
              gradient="from-red-500 to-rose-500"
            />
          </div>
        </div>

        {/* EXISTING CHARTS */}
        <div className="rounded-2xl bg-[var(--card-bg-2)] border border-[var(--card-bd)] p-6 shadow-lg mt-6">
          <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
            <PieChartCard
              title="Rating Distribution"
              data={ratingDistribution || []}
            />
            <BarChartCard
              title="Market Presence by Category"
              data={categories || []}
            />
          </div>
        </div>

        <div className="rounded-2xl bg-[var(--card-bg-2)] border border-[var(--card-bd)] p-6 shadow-lg mt-6">
          <BarChartCard
            title="Market Presence by Brand — Banks"
            data={banksMarket || []}
            getBarColor={getBankColor}
          />
        </div>

        {/* POPULAR TIMINGS */}
        <div className="chart-card rounded-2xl p-6 mt-6">
          <div className="flex justify-between items-center mb-4">
            <h3 style={{ color: "var(--title-tx)" }} className="text-base font-semibold">
              Popular Timings
            </h3>
            <div className="flex gap-2">
              <button
                onClick={() => setFootfallView("weekday")}
                style={footfallView === "weekday"
                  ? { background: "#3b82f6", color: "#fff" }
                  : { background: "var(--card-bg-2)", color: "var(--body-tx)", border: "1px solid var(--card-bd)" }}
                className="px-4 py-1 rounded-lg text-sm transition-colors"
              >
                Weekday
              </button>
              <button
                onClick={() => setFootfallView("weekend")}
                style={footfallView === "weekend"
                  ? { background: "#3b82f6", color: "#fff" }
                  : { background: "var(--card-bg-2)", color: "var(--body-tx)", border: "1px solid var(--card-bd)" }}
                className="px-4 py-1 rounded-lg text-sm transition-colors"
              >
                Weekend
              </button>
            </div>
          </div>

          <AreaChartCard
            title=""
            data={activeFootfallData}
            xKey="time"
            dataKey="value"
          />
        </div>

        {/* HEATMAP */}
        <div className="chart-card rounded-2xl p-6 mt-6">
          <h3 style={{ color: "var(--title-tx)" }} className="text-base font-semibold mb-6">
            Weekly Footfall Heatmap
          </h3>

          <div className="overflow-x-auto">
            <div className="grid grid-cols-[100px_repeat(17,1fr)] gap-2 text-xs min-w-[900px]">
              <div></div>
              {hours.map((hour) => (
                <div key={hour} style={{ color: "var(--muted-tx)" }} className="text-center">
                  {hour}
                </div>
              ))}

              {Object.entries(activeHeatmap).map(
                ([day, values]: [string, number[]]) => (
                  <>
                    <div key={day} style={{ color: "var(--body-tx)" }} className="font-medium">
                      {day}
                    </div>
                    {values.map((val: number, idx: number) => (
                      <div
                        key={`${day}-${idx}`}
                        className={`${getHeatColor(val)} text-white text-center py-2 rounded-lg`}
                      >
                        {val}
                      </div>
                    ))}
                  </>
                )
              )}
            </div>
          </div>
        </div>

      </div>
    </div>
  );
}