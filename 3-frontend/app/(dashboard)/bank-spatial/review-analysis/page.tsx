"use client";

import { useEffect, useState } from "react";
import DashboardTopbar from "@/components/layout/DashboardTopbar";
import { Layers,
  Blocks,
  Globe,
  Map,
  Users,
  Star,} from "lucide-react";
import GlassStatCard from "@/components/ui/StatCard";
import PieChartCard from "@/components/analytics/charts/PieChartCard";
import BarChartCard from "@/components/analytics/charts/BarChartCard";
import OutletRankingTable from "@/components/analytics/tables/OutletRankingTable";
import SentimentGlassBar from "@/components/analytics/metrics/SentimentGlassBar";
import TopicSentimentGlass from "@/components/analytics/charts/TopicSentimentGlass";
import BankSentimentGlass from "@/components/analytics/charts/BankSentimentGlass";
import { getBankColor } from "@/lib/bankColors";
import { 
    getBankSpatialSentimentKPIs, 
    getBankSpatialSentimentSplit,
    getBankSpatialSentimentDistribution,
    getBankSpatialBankReviews,
    getBankSpatialBankOutlets,
    getBankSpatialBankSentiment,
    getBankSpatialBankCommentsByTopic,
    getBankSpatialBankSentimentBreakdown,
    getBankSpatialBankSentimentBreakdownBanks,
    getBankSpatialBankTopicSentimentPercentage,
    getBankSpatialRatingDistribution,
    getFilters } 
from "@/lib/bankSpatial";
import FilterSelect from "@/components/filters/FilterSelect";


interface FiltersResponse {
  clusters: string[];
  sub_clusters: string[];
  zones: string[];
  countries: string[];
  categories: string[];
}


export default function BankingSpatialReviewAnalysisPage() {
    const [kpis, setKpis] = useState<any>(null);
    const [sentimentSplit, setSentimentSplit] = useState<any>(null);
    const [sentimentDistribution, setSentimentDistribution] = useState<any>(null);
    const [banksReviews, setBanksReviews] = useState<any>(null);
    const [outletRanking, setOutletRanking] = useState<any>(null);
    const [sentimentAnalysis, setSentimentAnalysis] = useState<any>(null);
    const [banksCommentsByTopic, setBanksCommentsByTopic] = useState<any>(null);
    const [sentimentBreakdown, setSentimentBreakdown] = useState<any>(null);
    const [sentimentBreakdownBanks, setSentimentBreakdownBanks] = useState<any>(null);
    const [topicSentimentPercentage, setTopicSentimentPercentage] = useState<any>(null);
    const [ratingDistribution, setRatingDistribution] = useState<any>(null);
    const [loading, setLoading] = useState(true);

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

    useEffect(() => {
        async function loadKPIs() {
            setLoading(true); 

            try {
                const data = await getBankSpatialSentimentKPIs(selectedFilters);
                setKpis(data);
            } catch (err) {
                console.error(err);
            } finally {
                setLoading(false);
            }
        }

        loadKPIs();
    }, [selectedFilters]);


    useEffect(() => {
        async function loadSentimentSplit() {
            setLoading(true); 

            try {
                const data = await getBankSpatialSentimentSplit(selectedFilters);
                setSentimentSplit(data);
            } catch (err) {
                console.error(err);
            } finally {
                setLoading(false);
            }
        }

        loadSentimentSplit();
    }, [selectedFilters]);


    useEffect(() => {
        async function loadSentimentDistribution() {
            setLoading(true); 

            try {
                const data = await getBankSpatialSentimentDistribution(selectedFilters);
                setSentimentDistribution(data);
            } catch (err) {
                console.error(err);
            } finally {
                setLoading(false);
            }
        }

        loadSentimentDistribution();
    }, [selectedFilters]);


    useEffect(() => {
        async function loadBanksReviews() {
            setLoading(true);

            try {
                const data = await getBankSpatialBankReviews(selectedFilters);
                setBanksReviews(data);
            } catch (err) {
                console.error(err);
            } finally {
                setLoading(false);
            }
        }

        loadBanksReviews();
    }, [selectedFilters]);


    useEffect(() => {
        async function loadBanksOutlets() {
            setLoading(true);

            try {
                const data = await getBankSpatialBankOutlets(selectedFilters);
                setOutletRanking(data);
            } catch (err) {
                console.error(err);
            } finally {
                setLoading(false);
            }
        }

        loadBanksOutlets();
    }, [selectedFilters]);


    useEffect(() => {
        async function loadSentimentAnalysis() {
            setLoading(true);

            try {
                const data = await getBankSpatialBankSentiment(selectedFilters);
                setSentimentAnalysis(data);
            } catch (err) {
                console.error(err);
            } finally {
                setLoading(false);
            }
        }

        loadSentimentAnalysis();
    }, [selectedFilters]);

    useEffect(() => {
        async function loadBanksCommentsByTopic() {
            setLoading(true);

            try {
                const data = await getBankSpatialBankCommentsByTopic(selectedFilters);
                setBanksCommentsByTopic(data);
            } catch (err) {
                console.error(err);
            } finally {
                setLoading(false);
            }
        }

        loadBanksCommentsByTopic(); 
    }, [selectedFilters]);

    useEffect(() => {
        async function loadSentimentBreakdown() {
            setLoading(true);

            try {
                const data = await getBankSpatialBankSentimentBreakdown(selectedFilters);
                setSentimentBreakdown(data);
            } catch (err) {
                console.error(err);
            } finally {
                setLoading(false);
            }
        }

        loadSentimentBreakdown();
    }, [selectedFilters]);


    useEffect(() => {
        async function loadSentimentBreakdownBanks() {
            setLoading(true);

            try {
                const data = await getBankSpatialBankSentimentBreakdownBanks(selectedFilters);
                setSentimentBreakdownBanks(data);
            } catch (err) {
                console.error(err);
            } finally {
                setLoading(false);
            }
        }    

        loadSentimentBreakdownBanks();
    }, [selectedFilters]);


    useEffect(() => {
        async function loadTopicSentimentPercentage() {
            setLoading(true);

            try {
                const data = await getBankSpatialBankTopicSentimentPercentage(selectedFilters);
                setTopicSentimentPercentage(data);
            } catch (err) {
                console.error(err);
            } finally {
                setLoading(false);
            }
        }

        loadTopicSentimentPercentage();
    }, [selectedFilters]);


    useEffect(() => {
        async function loadRatingDistribution() {
            setLoading(true);

            try {
                const data = await getBankSpatialRatingDistribution(selectedFilters);
                setRatingDistribution(data);
            } catch (err) {
                console.error(err);
            } finally {
                setLoading(false);
            }
        }

        loadRatingDistribution();
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

    /* =========================
     Helper: Build Dropdown Options
    ========================== */
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
      <div className="p-8">
        {/* ========================= FILTER PANEL ========================== */}
        <div className="relative z-50 rounded-2xl bg-[var(--card-bg)] p-6 shadow-xl border border-[var(--card-bd)] mb-8">

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
                className="
                px-5 py-2 text-sm 
                bg-white text-slate-900 
                font-medium 
                rounded-xl 
                hover:bg-slate-200 
                transition
                "
            >
                Reset Filters
            </button>
            </div>
        </div>


        <div className="rounded-2xl bg-[var(--card-bg-2)] border border-[var(--card-bd)] p-6 shadow-lg">
          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-5 gap-6">

                <GlassStatCard
                    title="Total Reviews"
                    value={kpis?.total_comments}
                    loading={loading}
                    icon={<Blocks size={18} />}
                    gradient="from-emerald-500 to-teal-500"
                />

                <GlassStatCard
                    title="Positive Reviews"
                    value={kpis?.positive_comments}
                    loading={loading}
                    icon={<Star size={18} />}
                    gradient="from-amber-500 to-orange-500"
                />

                <GlassStatCard
                    title="Negative Reviews"
                    value={kpis?.negative_comments}
                    loading={loading}
                    icon={<Users size={18} />}
                    gradient="from-amber-500 to-orange-500"
                />

                <GlassStatCard
                    title="Average Sentiment Score"
                    value={kpis?.avg_sentiment_score}
                    loading={loading}
                    icon={<Star size={18} />}
                    gradient="from-amber-500 to-orange-500"
                />

                <GlassStatCard
                    title="Average Rating"
                    value={kpis?.average_rating}
                    loading={loading}
                    icon={<Star size={18} />}
                    gradient="from-amber-500 to-orange-500"
                />
            </div>
        </div>

        <div className="rounded-2xl bg-[var(--card-bg-2)] border border-[var(--card-bd)] p-6 shadow-lg mt-6">
            <SentimentGlassBar data={sentimentAnalysis} />
        </div>

        <div className="rounded-2xl bg-[var(--card-bg-2)] border border-[var(--card-bd)] p-6 shadow-lg mt-6">
            <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
                <PieChartCard
                    title="Sentiment Split"
                    data={sentimentSplit || []}
                />

                <BarChartCard
                    title="Sentiment Score Distribution"
                    data={sentimentDistribution || []}
                />
            </div>
        </div>

        <div className="rounded-2xl bg-[var(--card-bg-2)] border border-[var(--card-bd)] p-6 shadow-lg mt-6">
            <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
                <PieChartCard
                    title="Topic Sentiment Distribution"
                    data={topicSentimentPercentage || []}
                />

                <PieChartCard
                    title="Rating Distribution"
                    data={ratingDistribution || []}
                />
            </div>
        </div>

        <div className="rounded-2xl bg-[var(--card-bg-2)] border border-[var(--card-bd)] p-6 shadow-lg mt-6">
            <BarChartCard
                title="Reviews per each Banks"
                data={banksReviews || []}
                getBarColor={getBankColor}
            />
        </div>

        <div className="rounded-2xl bg-[var(--card-bg-2)] border border-[var(--card-bd)] p-6 shadow-lg mt-6">
            <BankSentimentGlass  data={sentimentBreakdownBanks || []} />
        </div>

        <div className="rounded-2xl bg-[var(--card-bg-2)] border border-[var(--card-bd)] p-6 shadow-lg mt-6">
            <TopicSentimentGlass data={sentimentBreakdown || []} />
        </div>

        {outletRanking && (
            <div className="grid grid-cols-1 lg:grid-cols-2 gap-6 mt-6">
                <div className="rounded-2xl bg-[var(--card-bg-2)] border border-[var(--card-bd)] p-6 shadow-lg mt-6">
                    <OutletRankingTable
                    title="Top 10 Highest Rated"
                    type="top"
                    data={outletRanking.top_10_highest_rated}
                    />
                </div>

                <div className="rounded-2xl bg-[var(--card-bg-2)] border border-[var(--card-bd)] p-6 shadow-lg mt-6">
                    <OutletRankingTable
                    title="Bottom 10 Lowest Rated"
                    type="bottom"
                    data={outletRanking.bottom_10_lowest_rated}
                    />
                </div>
            </div>
        )}
      </div>
    </div>
  );
}
