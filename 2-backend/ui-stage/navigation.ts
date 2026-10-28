import type { LucideIcon } from "lucide-react";

export type NavItem = {
  label: string;
  href: string;
  icon: LucideIcon;
  roles?: string[]; // optional role restriction
};

import {
  LayoutDashboard,
  BarChart3,
  Utensils,
  Map,
  Zap,
  Star,
  BrainCircuit,
  FileDown,
  TrendingUp,
  Users,
  Puzzle,
  BookOpen,
  ClipboardList,
  Gauge,
  Search,
  MessageSquareText,
  Share2,
  Activity,
  LineChart,
  AreaChart,
  LayoutGrid,
  Sparkles,
  Lightbulb,
  Image as ImageIcon,
  AtSign,
  Linkedin,
  Hash,
  Play,
  Megaphone,
} from "lucide-react";

/**
 * Navigation grouped by dashboard type
 */
export const dashboardNavigation: Record<string, NavItem[]> = {
  banking: [
    { label: "Overview", href: "/bank-spatial", icon: LayoutDashboard },
    { label: "Spatial Intelligence", href: "/bank-spatial/spatial-intelligence", icon: Map },
    { label: "Review Analysis", href: "/bank-spatial/review-analysis", icon: Star },
    { label: "Ask Analytics Platform", href: "/bank-spatial/ask-assistant", icon: BrainCircuit },
  ],

  horeca: [
    { label: "Overview", href: "/horeca", icon: LayoutDashboard },
    { label: "Spatial Intelligence", href: "/horeca/spatial-intelligence", icon: Map },
    { label: "Review Analysis", href: "/horeca/review-analysis", icon: Star },
    { label: "Menu Analysis", href: "/horeca/menu-analysis", icon: Utensils },
    { label: "Horeca Deep Dive", href: "/horeca/deep-dive", icon: BarChart3 },
    { label: "Ask Analytics Platform", href: "/horeca/ask-assistant", icon: BrainCircuit },
  ],

  pricing: [
    { label: "Pricing", href: "/pricing/sales", icon: TrendingUp },
    { label: "Digital Shelf", href: "/pricing/brand-visibility", icon: LayoutGrid },
    { label: "Trended Data", href: "/pricing/availability", icon: AreaChart },
    { label: "Hero SKU", href: "/pricing/hero-sku-trend", icon: Activity },
    { label: "Hero SKU Graph", href: "/pricing/hero-sku-trend-graph", icon: LineChart },
    { label: "Raw Data", href: "/pricing/explore", icon: FileDown },
    { label: "Ask Analytics Platform", href: "/pricing/ask-assistant", icon: BrainCircuit },
    { label: "Glossary", href: "/pricing/glossary", icon: BookOpen },
  ],

  digitalBrandHealth: [
    { label: "BrandIQ Overview", href: "/digital-brand-health", icon: ClipboardList },
    { label: "AI Score", href: "/digital-brand-health/ai-score", icon: Gauge },
    { label: "Search Intelligence", href: "/digital-brand-health/search-data", icon: Search },
    { label: "Review Analysis", href: "/digital-brand-health/review-analysis", icon: Star },
    { label: "Social Analysis", href: "/digital-brand-health/social-analysis", icon: Share2 },
    { label: "Ask Analytics Platform", href: "/digital-brand-health/ask-assistant", icon: MessageSquareText },
  ],

  bankBrandHealth: [
    { label: "BrandIQ Overview", href: "/bank-brand-health", icon: ClipboardList },
    { label: "AI Score", href: "/bank-brand-health/ai-score", icon: Gauge },
    { label: "Search Intelligence", href: "/bank-brand-health/search-data", icon: Search },
    { label: "Review Analysis", href: "/bank-brand-health/review-analysis", icon: Star },
    { label: "Social Analysis", href: "/bank-brand-health/social-analysis", icon: Share2 },
    { label: "Ask Analytics Platform", href: "/bank-brand-health/ask-assistant", icon: MessageSquareText },
  ],

  dataCollection: [
    { label: "Instagram", href: "/data-collection/instagram", icon: AtSign },
    { label: "LinkedIn", href: "/data-collection/linkedin", icon: Linkedin },
    { label: "Twitter", href: "/data-collection/twitter", icon: Hash },
    { label: "TikTok", href: "/data-collection/tiktok", icon: Play },
  ],

  ev: [
    { label: "Overview", href: "/ev", icon: LayoutDashboard },
    { label: "Demand Analysis", href: "/ev/demand", icon: Zap },
    { label: "Competitors", href: "/ev/competitors", icon: BarChart3 },
  ],

  ceerCampaign: [
    { label: "Launch overview", href: "/ceer-campaign", icon: Megaphone },
    { label: "Post performance", href: "/ceer-campaign/content", icon: BarChart3 },
    { label: "Audience comments", href: "/ceer-campaign/audience", icon: MessageSquareText },
  ],

  realEstate: [
    { label: "BrandIQ Overview", href: "/real-estate", icon: ClipboardList },
    { label: "AI Score", href: "/real-estate/ai-score", icon: Gauge },
    { label: "Search Intelligence", href: "/real-estate/search-data", icon: Search },
    { label: "Review Analysis", href: "/real-estate/review-analysis", icon: Star },
    { label: "Social Analysis", href: "/real-estate/social-analysis", icon: Share2 },
    { label: "Ask Analytics Platform", href: "/real-estate/ask-assistant", icon: MessageSquareText },
  ],

  saudiRealEstate: [
    { label: "BrandIQ Overview", href: "/saudi-real-estate", icon: ClipboardList },
    { label: "AI Score", href: "/saudi-real-estate/ai-score", icon: Gauge },
    { label: "Search Intelligence", href: "/saudi-real-estate/search-data", icon: Search },
    { label: "Review Analysis", href: "/saudi-real-estate/review-analysis", icon: Star },
    { label: "Social Analysis", href: "/saudi-real-estate/social-analysis", icon: Share2 },
    { label: "Ask Analytics Platform", href: "/saudi-real-estate/ask-assistant", icon: MessageSquareText },
  ],

  trendsRealEstate: [
    { label: "Overview", href: "/trends-real-estate", icon: LayoutDashboard },
    { label: "AI Assistant", href: "/trends-real-estate/ai-assistant", icon: BrainCircuit },
    { label: "Trends Explorer", href: "/trends-real-estate/trends-explorer", icon: TrendingUp },
    { label: "Brand Intelligence", href: "/trends-real-estate/brand-intelligence", icon: Sparkles },
    { label: "Idea Testing", href: "/trends-real-estate/idea-testing", icon: Lightbulb },
    { label: "Visual Intelligence", href: "/trends-real-estate/visual-intelligence", icon: ImageIcon },
  ],

  foodIntelligence: [
    { label: "Overview", href: "/food-intelligence", icon: LayoutDashboard },
    { label: "AI Assistant", href: "/food-intelligence/ai-assistant", icon: BrainCircuit },
    { label: "Trends Explorer", href: "/food-intelligence/trends-explorer", icon: TrendingUp },
    { label: "Brand Intelligence", href: "/food-intelligence/brand-intelligence", icon: Sparkles },
    { label: "Idea Testing", href: "/food-intelligence/idea-testing", icon: Lightbulb },
    { label: "Visual Intelligence", href: "/food-intelligence/visual-intelligence", icon: ImageIcon },
  ],

  admin: [
    { label: "Users", href: "/admin", icon: Users },
    { label: "Services", href: "/admin/services", icon: Puzzle },
    { label: "Products", href: "/admin/products", icon: LayoutGrid },
  ],
};
