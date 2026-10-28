"use client";

import { useEffect, useState } from "react";
import DashboardTopbar from "@/components/layout/DashboardTopbar";
import dynamic from "next/dynamic";
import { getBankSpatialMapsData, getFilters } from "@/lib/bankSpatial";
import FilterSelect from "@/components/filters/FilterSelect";

/* =========================
   🔥 SSR SAFE MAP IMPORTS
========================= */

const LocationMap = dynamic(
  () => import("@/components/maps/LocationMap"),
  { ssr: false }
);

const PopulationDensityMap = dynamic(
  () => import("@/components/maps/PopulationDensityMap"),
  { ssr: false }
);

interface FiltersResponse {
  clusters: string[];
  sub_clusters: string[];
  zones: string[];
  countries: string[];
  categories: string[];
}

export default function BankingSpatialIntelligencePage() {
  const [mapData, setMapData] = useState<any[]>([]);
  const [loading, setLoading] = useState(true);
  const [activeTab, setActiveTab] = useState<"locations" | "density">("locations");

  const [filters, setFilters] = useState<FiltersResponse | null>(null);

  const [selectedFilters, setSelectedFilters] = useState({
    cluster: "",
    sub_cluster: "",
    zone: "",
    country: "",
    category: "",
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
        const data = await getBankSpatialMapsData(selectedFilters);
        setMapData(data);
      } catch (err) {
        console.error("Failed to load map data", err);
      } finally {
        setLoading(false);
      }
    }

    loadMapData();
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

  const buildOptions = (items: string[], allLabel: string) => {
    return [
      { label: allLabel, value: "" },
      ...items.map((item) => ({
        label: item,
        value: item,
      })),
    ];
  };

  return (
    <div className="min-h-screen bg-transparent">

      <DashboardTopbar
        title="Banking Spatial Intelligence"
      />

      <div className="p-8 space-y-6">

        {/* ================= FILTER PANEL ================= */}
        <div className="relative z-50 rounded-2xl bg-[var(--card-bg)] p-6 shadow-xl border border-[var(--card-bd)]">

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
                label="Country"
                value=""
                onChange={(val) => handleChange("country", val)}
                options={buildOptions(["Dubai"], "Emirates")}
                />

              <FilterSelect
                label="Brands"
                value=""
                onChange={(val) => handleChange("country", val)}
                options={buildOptions(["ENBD", "DIB", "HSBC", "ADCB"], "Brands")}
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
              className="px-5 py-2 text-sm bg-white text-slate-900 font-medium rounded-xl hover:bg-slate-200 transition"
            >
              Reset Filters
            </button>
          </div>
        </div>

        {/* ================= TAB SWITCH ================= */}
        <div className="flex gap-4">
          <button
            onClick={() => setActiveTab("locations")}
            style={activeTab === "locations"
              ? { background: "#3b82f6", color: "#fff", boxShadow: "0 2px 8px rgba(59,130,246,0.3)" }
              : { background: "var(--card-bg)", color: "var(--body-tx)", border: "1px solid var(--card-bd)" }}
            className="px-6 py-2 rounded-xl font-medium transition-colors"
          >
            Locations Map
          </button>

          <button
            onClick={() => setActiveTab("density")}
            style={activeTab === "density"
              ? { background: "#3b82f6", color: "#fff", boxShadow: "0 2px 8px rgba(59,130,246,0.3)" }
              : { background: "var(--card-bg)", color: "var(--body-tx)", border: "1px solid var(--card-bd)" }}
            className="px-6 py-2 rounded-xl font-medium transition-colors"
          >
            Population Density
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
                <LocationMap
                  data={mapData}
                  selectedZone={selectedFilters.zone}
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
