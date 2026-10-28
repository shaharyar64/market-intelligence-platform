"use client";

import { useEffect, useState } from "react";
import DashboardTopbar from "@/components/layout/DashboardTopbar";
import dynamic from "next/dynamic";
import { 
  getFilters,
  getHorecaSpatialMaps
} from "@/lib/horecaSpatial";
import FilterSelect from "@/components/filters/FilterSelect";
import FilterRating from "@/components/filters/FilterRating";

/* =========================
   🔥 SSR SAFE MAP IMPORTS
========================= */

const HorecaMap = dynamic(
  () => import("@/components/maps/HorecaMap"),
  { ssr: false }
);

const PopulationDensityMap = dynamic(
  () => import("@/components/maps/PopulationDensityMap"),
  { ssr: false }
);

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

export default function BankingSpatialIntelligencePage() {
  const [mapData, setMapData] = useState<any[]>([]);
  const [loading, setLoading] = useState(true);
  const [activeTab, setActiveTab] = useState<"locations" | "density">("locations");

  const [filters, setFilters] = useState<FiltersResponse | null>(null);

  const [selectedFilters, setSelectedFilters] = useState<SelectedFilters>({
    cuisine: [],
    horeca_type: [],
    price_range: [],
    min_rating: undefined
});

  /* =========================
     Load Filters (Once)
  ========================== */
  useEffect(() => {
    async function loadFilters() {
      try {
        const res = await getFilters();
        setFilters(res);
      } catch (err) {
        console.error("Failed to load filters", err);
      }
    }

    loadFilters();
  }, []);


  /* =========================
     Load Map Data on Filter Change
  ========================== */
  useEffect(() => {
    async function loadMapData() {
      setLoading(true);

      try {
        const data = await getHorecaSpatialMaps(selectedFilters);
        setMapData(data);
      } catch (err) {
        console.error("Failed to load map data", err);
      } finally {
        setLoading(false);
      }
    }

    loadMapData();
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

  return (
    <div className="min-h-screen bg-transparent">

      <DashboardTopbar
        title="Horeca Spatial Intelligence"
      />

      <div className="p-8 space-y-6">

        {/* ================= FILTER PANEL ================= */}

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
        

        {/* ================= TAB SWITCH ================= */}
        <div className="flex gap-4">
          <button
            onClick={() => setActiveTab("locations")}
            className={`px-6 py-2 rounded-xl font-medium transition ${
              activeTab === "locations"
                ? "bg-[var(--card-bg)] text-white shadow-md"
                : "bg-white text-slate-600 border"
            }`}
          >
            Locations Map
          </button>

        </div>

        {/* ================= MAP PANEL ================= */}
        <div className="relative bg-white rounded-2xl shadow-sm border border-slate-200 p-4 min-h-[800px] overflow-hidden">

          {loading ? (
            <div className="absolute inset-0 flex flex-col items-center justify-center gap-6 bg-white z-10">
              <img
                src="/x.svg"
                alt="Loading"
                className="w-14 h-14 animate-pulse"
              />
              <p className="text-slate-500 text-sm animate-pulse">
                Loading spatial intelligence...
              </p>
            </div>
          ) : (
            <div className="min-h-[750px]">
              {activeTab === "locations" && (
                <HorecaMap
                  data={mapData}
                />
              )}

              {activeTab === "density" && (
                <PopulationDensityMap
                  data={mapData}
                />
              )}
            </div>
          )}
        </div>

      </div>
    </div>
  );
}
