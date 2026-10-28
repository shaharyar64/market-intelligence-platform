"use client";

import { useEffect, useState } from "react";
import DashboardTopbar from "@/components/layout/DashboardTopbar";
import { CookingPot, Soup, SaudiRiyal } from "lucide-react";
import GlassStatCard from "@/components/ui/StatCard";
import PieChartCard from "@/components/analytics/charts/PieChartCard";
import BarChartCard from "@/components/analytics/charts/BarChartCard";
import HorizontalBarChartCard from "@/components/analytics/charts/HorizontalBarChartCard";
import FilterSelect from "@/components/filters/FilterSelect";
import FilterRating from "@/components/filters/FilterRating";
import {
  getFilters,
  getRiceKpis,
  getRicePriceDistribution,
  getTopRiceDishes,
  getRiceByCuisine,
  getRiceMenuMix
} from "@/lib/horecaSpatial";


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

export default function HorecaMenuAnalysis() {

  /* ================= STATE ================= */

  const [riceKpis, setRiceKpis] = useState<any>(null);
  const [priceDistribution, setPriceDistribution] = useState<any[]>([]);
  const [topRiceDishes, setTopRiceDishes] = useState<any[]>([]);
  const [riceByCuisine, setRiceByCuisine] = useState<any[]>([]);
  const [menuMix, setMenuMix] = useState<any>(null);

  const [loading, setLoading] = useState(true);
  const [filters, setFilters] = useState<FiltersResponse | null>(null);
  const [selectedFilters, setSelectedFilters] = useState<SelectedFilters>({
    cuisine: [],
    horeca_type: [],
    price_range: [],
    min_rating: undefined
});

  /* ================= LOAD DATA ================= */

  // Load filters on mount
  useEffect(() => {
    async function loadFilters() {
      const data = await getFilters();
      setFilters(data);
      setLoading(false);
    }
    loadFilters();
  }, []);

  useEffect(() => {
    async function loadRiceAnalytics() {
      try {
        setLoading(true);

        const [
          kpis,
          priceDist,
          topDishes,
          cuisineData,
          mix
        ] = await Promise.all([
          getRiceKpis(),
          getRicePriceDistribution(),
          getTopRiceDishes(),
          getRiceByCuisine(),
          getRiceMenuMix()
        ]);

        setRiceKpis(kpis);
        setPriceDistribution(priceDist);
        setTopRiceDishes(topDishes);
        setRiceByCuisine(cuisineData);
        setMenuMix(mix);

        /* temporary console logs for verification */
        console.log("Rice KPIs:", kpis);
        console.log("Rice Price Distribution:", priceDist);
        console.log("Top Rice Dishes:", topDishes);
        console.log("Rice by Cuisine:", cuisineData);
        console.log("Rice Menu Mix:", mix);

      } catch (err) {
        console.error("Failed to load rice analytics", err);
      } finally {
        setLoading(false);
      }
    }

    loadRiceAnalytics();
  }, []);

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

  /* ================= UI ================= */

  return (
    <div className="min-h-screen bg-transparent">

      <DashboardTopbar
        title="Horeca Spatial Intelligence"
      />

      <div className="p-8 space-y-6">
        {/* ── Filter Panel ─────────────────────────────────────────────────── */}
        <div className="rounded-2xl bg-[var(--card-bg)] p-6 shadow-xl border border-[var(--card-bd)]">
        {filters ? (
            <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
            <FilterSelect
                label="Cuisine"
                value={selectedFilters.cuisine[0] || ""}
                onChange={(val) => handleSelectChange("cuisine", val)}
                options={buildOptions(filters.cuisine, "All Cuisines")}
            />
            <FilterSelect
                label="Horeca Type"
                value={selectedFilters.horeca_type[0] || ""}
                onChange={(val) => handleSelectChange("horeca_type", val)}
                options={buildOptions(filters.horeca_type, "All Horeca Types")}
            />
            <FilterSelect
                label="Price Range"
                value={selectedFilters.price_range[0] || ""}
                onChange={(val) => handleSelectChange("price_range", val)}
                options={buildOptions(filters.price_range, "All Price Ranges")}
            />
            <FilterRating
                label="Minimum Rating"
                min={filters.rating.min}
                max={filters.rating.max}
                value={selectedFilters.min_rating ?? filters.rating.min}
                onChange={handleRatingChange}
            />
            </div>
        ) : (
            // Filter skeleton while options are loading
            <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
            {Array.from({ length: 4 }).map((_, i) => (
                <div
                key={i}
                className="h-10 rounded-xl bg-slate-700 animate-pulse"
                />
            ))}
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
      </div>

      <div className="p-8">
        {/* KPIs */}
        <div className="rounded-2xl bg-[var(--card-bg-2)] border border-[var(--card-bd)] p-6 shadow-lg">
          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-6">
            <GlassStatCard
              title="Total Rice Dishes"
              value={riceKpis?.total_rice_items}
              loading={loading}
              icon={<CookingPot size={18} />}
              gradient="from-emerald-500 to-teal-500"
            />
            <GlassStatCard
              title="Restaurants with Rice"
              value={riceKpis?.restaurants_with_rice}
              loading={loading}
              icon={<Soup size={18} />}
              gradient="from-amber-500 to-orange-500"
            />
            <GlassStatCard
              title="Average Rice Price"
              value={riceKpis?.avg_rice_price * 100}
              loading={loading}
              icon={<SaudiRiyal size={18} />}
              gradient="from-indigo-500 to-purple-500"
            />
          </div>
        </div>

        <div className="rounded-2xl bg-[var(--card-bg-2)] border border-[var(--card-bd)] p-6 shadow-lg mt-6">
            <div className="grid grid-cols-1 lg:grid-cols-[45%_53%] gap-6">

            {/* PIE CHART */}
            <PieChartCard
                title="Rice Menu Mix Percentage"
                data={menuMix ? menuMix.map((item: any) => ({
                name: item.name,
                value: item.percentage
                })) : []}
            />

            {/* PIE CHART */}
            <PieChartCard
                title="Top Rice Dishes by Restaurant Count"
                data={topRiceDishes ? topRiceDishes.map((item: any) => ({
                name: item.item_name,
                value: item.restaurant_count
                })) : []}
            />

            </div>
        </div>

        <div className="rounded-2xl bg-[var(--card-bg-2)] border border-[var(--card-bd)] p-6 shadow-lg mt-6">
            <HorizontalBarChartCard
            title="Rice Dishes by Cuisine"
            data={riceByCuisine ? riceByCuisine.map((item: any) => ({
                name: item.cuisine,
                value: item.rice_items
            })) : []}
            height={1250}
            loading={loading}
            />
        </div>

      </div>

    </div>
  );
}