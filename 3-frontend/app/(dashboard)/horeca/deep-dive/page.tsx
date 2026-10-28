"use client";

import { useEffect, useState } from "react";
import Image from "next/image";
import {
  getFilters,
  getHorecaSpatialRestaurants,
  getHorecaRestaurantDetails,
  getHorecaRestaurantNames
} from "@/lib/horecaSpatial";
import { Layers, Blocks, Globe, Map, Users, Star } from "lucide-react";
import GlassStatCard from "@/components/ui/StatCard";
import DashboardTopbar from "@/components/layout/DashboardTopbar";
import FilterSelect from "@/components/filters/FilterSelect";
import FilterRating from "@/components/filters/FilterRating";
import FilterSearchSelect from "@/components/filters/FilterSearchSelect";
import HeatmapCard from "@/components/analytics/charts/HeatmapCard"
import PieChartCard from "@/components/analytics/charts/PieChartCard";
import BarChartCard from "@/components/analytics/charts/BarChartCard";
import HorizontalBarChartCard from "@/components/analytics/charts/HorizontalBarChartCard";

/* ================= TYPES ================= */

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

interface Restaurant {
  name: string;
  horeca_type: string;
  main_category: string;
  city: string;
  rating: number;
  total_reviews: number;
  place_id: string;
  google_maps_url: string;
}

/* ================= COMPONENT ================= */

export default function HorecaDeepDive() {
  const [loading, setLoading] = useState(true);
  const [restaurants, setRestaurants] = useState<any>(null);
  const [restaurantDetails, setRestaurantDetails] = useState<any>(null);

  /* 🔧 TYPE FIX (restaurant names contain objects) */
  const [restaurantNames, setRestaurantNames] = useState<any[]>([]);

  const [filters, setFilters] = useState<FiltersResponse | null>(null);

  const [placeId, setPlaceId] = useState<string | null>("ChIJDe8DD0QdLz4RB6Bw0Hqr3OM");
  const [page, setPage] = useState(1);
  const pageSize = 25;

  const [selectedRestaurant, setSelectedRestaurant] = useState("");

  const [selectedFilters, setSelectedFilters] = useState<SelectedFilters>({
    cuisine: [],
    horeca_type: [],
    price_range: [],
    min_rating: undefined,
  });

  /* ================= API CALLS ================= */

  useEffect(() => {
    async function loadFilters() {
      const data = await getFilters();
      setFilters(data);
    }

    loadFilters();
  }, []);

  useEffect(() => {
    async function loadRestaurants() {
      setLoading(true);

      const data = await getHorecaSpatialRestaurants(
        selectedFilters,
        page,
        pageSize
      );

      setRestaurants(data);
      setLoading(false);
    }

    loadRestaurants();
  }, [selectedFilters, page]);

  useEffect(() => {
    if (!placeId) return;

    const loadRestaurants = async () => {
        try {
        setLoading(true);

        const data = await getHorecaRestaurantDetails(
            placeId,
            selectedFilters
        );

        setRestaurantDetails(data);
        } catch (error) {
        console.error("Failed to load restaurant details", error);
        } finally {
        setLoading(false);
        }
    };

    loadRestaurants();

    }, [placeId, selectedFilters]);

  useEffect(() => {
    async function loadRestaurantNames() {
      try {
        const data = await getHorecaRestaurantNames();
        setRestaurantNames(data);
      } catch (err) {
        console.error("Failed to load restaurant names", err);
      }
    }

    loadRestaurantNames();
  }, []);

  /* ================= NEW: AUTO SELECT DEFAULT RESTAURANT ================= */

  useEffect(() => {
    if (!restaurantNames.length || !placeId) return;

    const match = restaurantNames.find(
      (r: any) => r.place_id === placeId
    );

    if (match) {
      setSelectedRestaurant(match.place_id);
    }
  }, [restaurantNames, placeId]);

  /* ================= HANDLERS ================= */

  const handleSelectChange = (
    key: keyof SelectedFilters,
    value: string
  ) => {
    setPage(1);

    setSelectedFilters((prev) => ({
      ...prev,
      [key]: value ? [value] : [],
    }));
  };

  const handleRatingChange = (value: number) => {
    setPage(1);

    setSelectedFilters((prev) => ({
      ...prev,
      min_rating: value,
    }));
  };

  const handleRestaurantChange = (value: string) => {
    setSelectedRestaurant(value);
    setPlaceId(value);
  };

  const resetFilters = () => {
    setPage(1);

    setSelectedFilters({
      cuisine: [],
      horeca_type: [],
      price_range: [],
      min_rating: undefined,
    });
  };

  const buildOptions = (items: string[], label: string) => [
    { label, value: "" },
    ...items.map((item) => ({
      label: item,
      value: item,
    })),
  ];

  const restaurantOptions = [
    { label: "Search Restaurant...", value: "" },
    ...restaurantNames.map((r: any) => ({
      label: r.name,
      value: r.place_id,
    })),
  ];

  /* ================= UI ================= */

  return (
    <div className="min-h-screen bg-transparent">
      <DashboardTopbar
        title="Horeca Spatial Intelligence"
      />

      <div className="p-8 space-y-8">

        {/* ================= FILTER PANEL ================= */}

        <div className="rounded-2xl bg-[var(--card-bg)] p-6 shadow-xl border border-[var(--card-bd)]">

          {filters && (
            <div className="grid grid-cols-1 md:grid-cols-4 gap-4">

              <FilterSelect
                label="Cuisine"
                value={selectedFilters.cuisine[0] || ""}
                onChange={(val) =>
                  handleSelectChange("cuisine", val)
                }
                options={buildOptions(
                  filters.cuisine,
                  "All Cuisines"
                )}
              />

              <FilterSelect
                label="Horeca Type"
                value={selectedFilters.horeca_type[0] || ""}
                onChange={(val) =>
                  handleSelectChange("horeca_type", val)
                }
                options={buildOptions(
                  filters.horeca_type,
                  "All Horeca Types"
                )}
              />

              <FilterSelect
                label="Price Range"
                value={selectedFilters.price_range[0] || ""}
                onChange={(val) =>
                  handleSelectChange("price_range", val)
                }
                options={buildOptions(
                  filters.price_range,
                  "All Price Ranges"
                )}
              />

              <FilterRating
                label="Minimum Rating"
                min={filters.rating.min}
                max={filters.rating.max}
                value={
                  selectedFilters.min_rating ||
                  filters.rating.min
                }
                onChange={handleRatingChange}
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

        {/* ================= TABLE CARD ================= */}

        <div className="rounded-2xl bg-gradient-to-br from-[#0f172a] to-[#0b132b] p-6 shadow-xl border border-slate-700 backdrop-blur-md">

          <div className="overflow-x-auto">

            <table className="w-full text-sm text-slate-200">

              <thead className="bg-white/5 text-slate-300">
                <tr>
                  <th className="p-3 text-left font-semibold">Name</th>
                  <th className="p-3 text-left font-semibold">Horeca Type</th>
                  <th className="p-3 text-left font-semibold">Category</th>
                  <th className="p-3 text-left font-semibold">City</th>
                  <th className="p-3 text-left font-semibold">Rating</th>
                  <th className="p-3 text-left font-semibold">Reviews</th>
                </tr>
              </thead>

              <tbody>

                {loading && (
                  <tr>
                    <td colSpan={6} className="text-center p-6">
                      Loading restaurants...
                    </td>
                  </tr>
                )}

                {!loading && restaurants?.data?.length === 0 && (
                  <tr>
                    <td colSpan={6} className="text-center p-6">
                      No restaurants found
                    </td>
                  </tr>
                )}

                {!loading &&
                  restaurants?.data?.map((r: Restaurant) => (
                    <tr
                      key={r.place_id}
                      className="border-t border-white/10 hover:bg-white/5 transition"
                    >
                      <td className="p-3">
                        <a
                          href={r.google_maps_url}
                          target="_blank"
                          rel="noopener noreferrer"
                          className="text-blue-400 hover:underline"
                        >
                          {r.name}
                        </a>
                      </td>

                      <td className="p-3">{r.horeca_type}</td>
                      <td className="p-3">{r.main_category}</td>
                      <td className="p-3">{r.city}</td>
                      <td className="p-3">{r.rating}</td>
                      <td className="p-3">{r.total_reviews}</td>
                    </tr>
                  ))}

              </tbody>

            </table>

          </div>

          {/* ================= PAGINATION INSIDE CARD ================= */}

          <div className="flex justify-between items-center mt-6 pt-4 border-t border-white/10">

            <button
              disabled={page === 1}
              onClick={() => setPage((p) => p - 1)}
              className="px-4 py-2 bg-white/10 text-white rounded-lg border border-white/10 hover:bg-white/20 disabled:opacity-40 transition"
            >
              Previous
            </button>

            <span className="text-sm text-slate-300">
              Page {page}
            </span>

            <button
              disabled={!restaurants?.data?.length}
              onClick={() => setPage((p) => p + 1)}
              className="px-4 py-2 bg-white/10 text-white rounded-lg border border-white/10 hover:bg-white/20 disabled:opacity-40 transition"
            >
              Next
            </button>

          </div>
        </div>

        {/* ================= SEARCH RESTAURANT ================= */}

        <div className="rounded-2xl bg-[var(--card-bg)] p-6 shadow-xl border border-[var(--card-bd)]">
          <FilterSearchSelect
            label="Search Restaurant"
            value={selectedRestaurant}
            options={restaurantOptions}
            onChange={handleRestaurantChange}
          />
        </div>

        {/* ── Restaurant Overview ───────────────────────────────────────────── */}

        <div className="rounded-2xl bg-[var(--card-bg-2)] border border-[var(--card-bd)] p-6 shadow-lg">

        <h2 className="text-lg font-semibold text-white mb-6">
            Restaurant Overview
        </h2>

        {restaurantDetails?.restaurant && (
            <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">

            {/* Name */}
            <div className="bg-white/5 backdrop-blur-md border border-white/10 rounded-xl p-4 hover:bg-white/10 transition">
                <p className="text-xs text-slate-400">Name</p>
                <p className="text-white font-semibold mt-1">
                {restaurantDetails.restaurant.name}
                </p>
            </div>

            {/* Horeca Type */}
            <div className="bg-white/5 backdrop-blur-md border border-white/10 rounded-xl p-4 hover:bg-white/10 transition">
                <p className="text-xs text-slate-400">Horeca Type</p>
                <p className="text-white mt-1">
                {restaurantDetails.restaurant.horeca_type}
                </p>
            </div>

            {/* Category */}
            <div className="bg-white/5 backdrop-blur-md border border-white/10 rounded-xl p-4 hover:bg-white/10 transition">
                <p className="text-xs text-slate-400">Category</p>
                <p className="text-white mt-1">
                {restaurantDetails.restaurant.main_category}
                </p>
            </div>

            {/* City */}
            <div className="bg-white/5 backdrop-blur-md border border-white/10 rounded-xl p-4 hover:bg-white/10 transition">
                <p className="text-xs text-slate-400">City</p>
                <p className="text-white mt-1">
                {restaurantDetails.restaurant.city}
                </p>
            </div>

            {/* Price Range */}
            <div className="bg-white/5 backdrop-blur-md border border-white/10 rounded-xl p-4 hover:bg-white/10 transition">
                <p className="text-xs text-slate-400">Price Range</p>
                <p className="text-white mt-1">
                {restaurantDetails.restaurant.price_range}
                </p>
            </div>

            {/* Google Maps */}
            <div className="bg-white/5 backdrop-blur-md border border-white/10 rounded-xl p-4 hover:bg-white/10 transition">
                <p className="text-xs text-slate-400">Location</p>
                <a
                href={restaurantDetails.restaurant.google_maps_url}
                target="_blank"
                rel="noopener noreferrer"
                className="text-blue-400 hover:underline mt-1 block"
                >
                View on Google Maps
                </a>
            </div>

            </div>
        )}

        </div>

        {/* ── KPI Cards ────────────────────────────────────────────────────── */}
        <div className="rounded-2xl bg-[var(--card-bg-2)] border border-[var(--card-bd)] p-6 shadow-lg">
          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-6">
            <GlassStatCard
              title="Total Reviews"
              value={restaurantDetails?.review_kpis?.total_reviews}
              loading={loading}
              icon={<Blocks size={18} />}
              gradient="from-emerald-500 to-teal-500"
            />
            <GlassStatCard
              title="Positive Reviews"
              value={restaurantDetails?.review_kpis?.positive_reviews}
              loading={loading}
              icon={<Star size={18} />}
              gradient="from-amber-500 to-orange-500"
            />
            <GlassStatCard
              title="Negative Reviews"
              value={restaurantDetails?.review_kpis?.negative_reviews}
              loading={loading}
              icon={<Users size={18} />}
              gradient="from-rose-500 to-red-500"
            />
            <GlassStatCard
              title="Average Rating"
              value={restaurantDetails?.review_kpis?.avg_rating}
              loading={loading}
              icon={<Star size={18} />}
              gradient="from-violet-500 to-purple-500"
            />
          </div>
        </div>

        {/* ── Rating Distribution ───────────────────────────────────────────── */}
        <div className="rounded-2xl bg-[var(--card-bg-2)] border border-[var(--card-bd)] p-6 shadow-lg">
            <div className="grid grid-cols-1 lg:grid-cols-[33%_65%] gap-6">
            <PieChartCard
                title="Rating Distribution (%)"
                data={restaurantDetails?.rating_distribution.map((d: any) => ({ name: d.rating, value: d.percentage })) || []}
                loading={loading}
            />
            <BarChartCard
                title="Rating Distribution (Count)"
                data={restaurantDetails?.rating_distribution.map((d: any) => ({ name: d.rating, value: d.count })) || []}
                loading={loading}
            />
            </div>
        </div>

        {/* ── Topics ───────────────────────────────────────────────────────── */}
        <div className="rounded-2xl bg-[var(--card-bg-2)] border border-[var(--card-bd)] p-6 shadow-lg">
            <HorizontalBarChartCard
            title="Topics Wise Reviews"
            data={restaurantDetails?.review_topics || []}
            height={900}
            loading={loading}
            />
        </div>

        <div className="rounded-2xl bg-[var(--card-bg-2)] border border-[var(--card-bd)] p-6 shadow-lg mt-6">
            <HeatmapCard
            title="Restaurant Popular Times"
            data={restaurantDetails?.popular_times || []}
            xKey="x"
            yKey="y"
            valueKey="value"
            />
        </div>

        {/* ── Menu Items ───────────────────────────────────────── */}

        <div className="rounded-2xl bg-[var(--card-bg-2)] border border-[var(--card-bd)] p-6 shadow-lg">

        <h2 className="text-lg font-semibold text-white mb-6">
            Menu Items
        </h2>

        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-6">

            {restaurantDetails?.menu?.map((item: any, idx: number) => (

            <div
                key={idx}
                className="bg-white/5 backdrop-blur-md border border-white/10 rounded-xl overflow-hidden hover:bg-white/10 transition"
            >

                <div className="relative w-full h-40">

                <Image
                    src={item.image}
                    alt={item.item_name}
                    fill
                    className="object-cover"
                    sizes="(max-width:768px) 100vw, (max-width:1200px) 50vw, 25vw"
                />

                </div>

                <div className="p-4">

                <p className="text-white text-sm font-medium line-clamp-2">
                    {item.item_name}
                </p>

                <p className="text-slate-400 text-sm mt-1">
                    SAR {item.price_SAR}
                </p>

                </div>

            </div>

            ))}

        </div>

        </div>

      </div>
    </div>
  );
}


// ─── Small reusable error banner ─────────────────────────────────────────────

function ErrorBanner({ message }: { message: string }) {
  return (
    <div className="mb-4 rounded-lg bg-rose-900/40 border border-rose-700 px-4 py-2 text-sm text-rose-300">
      {message}
    </div>
  );
}