"use client";

import { useEffect, useState } from "react";
import DashboardTopbar from "@/components/layout/DashboardTopbar";
import { 
  getFilters, 
  getHorecaSpatialKPIs,
  getHorecaSpatialHorecaSplit,
  getHorecaSpatialHorecaPopular
} from "@/lib/horecaSpatial";
import { CookingPot, UserStar, Star, Utensils, SaudiRiyal } from "lucide-react";
import GlassStatCard from "@/components/ui/StatCard";
import FilterSelect from "@/components/filters/FilterSelect";
import FilterRating from "@/components/filters/FilterRating";
import PieChartCard from "@/components/analytics/charts/PieChartCard";
import BarChartCard from "@/components/analytics/charts/BarChartCard";
import HeatmapCard from "@/components/analytics/charts/HeatmapCard"

interface FiltersResponse {
  cuisine: string[];
  horeca_type: string[];
  price_range: string[];
  rating: {
    min: number;
    max: number;
  };
}

interface SelectedFilters {
  cuisine: string[];
  horeca_type: string[];
  price_range: string[];
  min_rating?: number;
}

export default function HorecaSpatialPage() {
  /* =========================
     STATE
  ========================== */

  const [loading, setLoading] = useState(true);
  const [kpis, setKpis] = useState<any>(null);
  const [horecaSplit, setHorecaSplit] = useState<any>(null);
  const [popularTimes, setPopularTimes] = useState<any>(null);
  const [filters, setFilters] = useState<FiltersResponse | null>(null);

  const [selectedFilters, setSelectedFilters] = useState<SelectedFilters>({
    cuisine: [],
    horeca_type: [],
    price_range: [],
    min_rating: undefined
  });

  /* =========================
     API CALLS
  ========================== */

  // Load filters on mount
  useEffect(() => {
    async function loadFilters() {
      const data = await getFilters();
      setFilters(data);
      setLoading(false);
    }
    loadFilters();
  }, []);

  // Load KPIs
  useEffect(() => {
    setLoading(true);
    getHorecaSpatialKPIs(selectedFilters)
      .then(setKpis)
      .finally(() => setLoading(false));
  }, [selectedFilters]);

  // Load horeca split
  useEffect(() => {
    setLoading(true);
    getHorecaSpatialHorecaSplit(selectedFilters)
      .then(setHorecaSplit)
      .finally(() => setLoading(false));
  }, [selectedFilters]);


  // Load popular times
  useEffect(() => {
    setLoading(true);
    getHorecaSpatialHorecaPopular(selectedFilters)
      .then(setPopularTimes)
      .finally(() => setLoading(false));
  }, [selectedFilters]);


  /* =========================
     HANDLERS
  ========================== */

  const handleSelectChange = (key: keyof SelectedFilters, value: string) => {
    setSelectedFilters((prev) => ({
      ...prev,
      [key]: value ? [value] : []
    }));
  };

  const handleRatingChange = (value: number) => {
    setSelectedFilters((prev) => ({
      ...prev,
      min_rating: value
    }));
  };

  const resetFilters = () => {
    setSelectedFilters({
      cuisine: [],
      horeca_type: [],
      price_range: [],
      min_rating: undefined
    });
  };

  const buildOptions = (items: string[], label: string) => [
    { label, value: "" },
    ...items.map((item) => ({
      label: item,
      value: item
    }))
  ];

  /* =========================
     UI
  ========================== */

  return (
    <div className="min-h-screen bg-transparent">
      <DashboardTopbar
        title="Horeca Spatial Intelligence"
      />

      <div className="p-8">

        {/* FILTER PANEL */}
        <div className="rounded-2xl bg-[var(--card-bg)] p-6 shadow-xl border border-[var(--card-bd)] mb-8">

          {filters && (
            <div className="grid grid-cols-1 md:grid-cols-4 gap-4">

              {/* CUISINE */}
              <FilterSelect
                label="Cuisine"
                value={selectedFilters.cuisine[0] || ""}
                onChange={(val) => handleSelectChange("cuisine", val)}
                options={buildOptions(filters.cuisine, "All Cuisines")}
              />

              {/* HORECA TYPE */}
              <FilterSelect
                label="Horeca Type"
                value={selectedFilters.horeca_type[0] || ""}
                onChange={(val) => handleSelectChange("horeca_type", val)}
                options={buildOptions(filters.horeca_type, "All Horeca Types")}
              />

              {/* PRICE RANGE */}
              <FilterSelect
                label="Price Range"
                value={selectedFilters.price_range[0] || ""}
                onChange={(val) => handleSelectChange("price_range", val)}
                options={buildOptions(filters.price_range, "All Price Ranges")}
              />

              {/* RATING */}
              <FilterRating
                label="Minimum Rating"
                min={filters.rating.min}
                max={filters.rating.max}
                value={selectedFilters.min_rating || filters.rating.min}
                onChange={handleRatingChange}
              />

            </div>
          )}

          {/* RESET BUTTON */}
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
          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-5 gap-6">
            <GlassStatCard
              title="Total Restaurants"
              value={kpis?.total_restaurants}
              loading={loading}
              icon={<Utensils size={18} />}
              gradient="from-emerald-500 to-teal-500"
            />
            <GlassStatCard
              title="Total Reviews"
              value={kpis?.total_reviews}
              loading={loading}
              icon={<UserStar size={18} />}
              gradient="from-amber-500 to-orange-500"
            />
            <GlassStatCard
              title="Average Price"
              value={kpis?.average_price}
              loading={loading}
              icon={<SaudiRiyal size={18} />}
              gradient="from-indigo-500 to-purple-500"
            />
            <GlassStatCard
              title="Average Rating"
              value={kpis?.avg_rating}
              loading={loading}
              icon={<Star size={18} />}
              gradient="from-pink-500 to-rose-500"
            />

            <GlassStatCard
              title="Average Menu Items"
              value={kpis?.average_menu_items}
              loading={loading}
              icon={<CookingPot size={18} />}
              gradient="from-blue-500 to-rose-500"
            />
          </div>
        </div>

        <div className="rounded-2xl bg-[var(--card-bg-2)] border border-[var(--card-bd)] p-6 shadow-lg mt-6">
          <div className="grid grid-cols-1 lg:grid-cols-[33%_65%] gap-6">

            {/* PIE CHART */}
            <PieChartCard
              title="Horeca Type Split"
              data={horecaSplit ? horecaSplit.map((item: any) => ({
                name: item.horeca_type,
                value: item.percentage
              })) : []}
            />

            {/* BAR CHART */}
            <BarChartCard
              title="Horeca Type Count"
              data={horecaSplit ? horecaSplit.map((item: any) => ({
                name: item.horeca_type,
                value: item.count
              })) : []}
            />

          </div>
        </div>

        <div className="rounded-2xl bg-[var(--card-bg-2)] border border-[var(--card-bd)] p-6 shadow-lg mt-6">
          <HeatmapCard
            title="Restaurant Popular Times"
            data={popularTimes}
            xKey="x"
            yKey="y"
            valueKey="value"
          />
        </div>

      </div>
    </div>
  );
}