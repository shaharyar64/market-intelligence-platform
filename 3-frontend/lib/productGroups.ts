import {
  BarChart3, BadgeDollarSign, TrendingUp, MapPin,
  Landmark, Building2, Utensils, Megaphone, LucideIcon,
} from "lucide-react";
import type { Service, Product, ProductKey } from "./user";

export type { ProductKey } from "./user";

export interface ProductMeta {
  key: ProductKey;
  label: string;
  tagline: string;
  gradient: string; // tailwind gradient stops, used when `color` is unset
  color?: string;    // backend-supplied override — a solid CSS color/hex, applied via inline style instead of `gradient`
  Icon: LucideIcon;
}

/**
 * Visual fallback for the four original products, used only when the
 * backend Product record's tagline/icon/color are still null (they were
 * seeded with just key/label/sort_order — see /admin/products). A newly
 * created 5th+ product with no visual override falls through to
 * DEFAULT_VISUAL below instead. Once the backend backfills real
 * tagline/icon/color values, those take priority and this map stops
 * mattering for brandiq/compiq/predictiq/geoiq.
 */
const VISUAL_FALLBACK: Record<string, { tagline: string; gradient: string; Icon: LucideIcon }> = {
  brandiq: {
    tagline: "Digital Brand Health — sentiment, share of voice and reputation tracking",
    gradient: "from-violet-500 to-indigo-600",
    Icon: BarChart3,
  },
  compiq: {
    tagline: "Pricing Intelligence — competitive pricing benchmarks across markets",
    gradient: "from-teal-400 to-cyan-600",
    Icon: BadgeDollarSign,
  },
  predictiq: {
    tagline: "Trends & Forecasting — demand signals and category trend forecasts",
    gradient: "from-rose-400 to-pink-600",
    Icon: TrendingUp,
  },
  geoiq: {
    tagline: "Spatial Intelligence — location analytics and spatial market mapping",
    gradient: "from-emerald-400 to-teal-600",
    Icon: MapPin,
  },
};

const DEFAULT_VISUAL = { tagline: "", gradient: "from-slate-400 to-slate-600", Icon: BarChart3 };

const ICON_BY_KEY: Record<string, LucideIcon> = {
  "bar-chart": BarChart3,
  "dollar-sign": BadgeDollarSign,
  "trending-up": TrendingUp,
  "map-pin": MapPin,
  landmark: Landmark,
  building: Building2,
  utensils: Utensils,
};

const SERVICE_VISUAL_BY_KEY: Record<string, { Icon: LucideIcon; gradient: string }> = {
  megaphone: { Icon: Megaphone, gradient: "from-violet-500 to-fuchsia-600" },
};

/** Resolves the icon and visual treatment stored on an admin-managed service record. */
export function getServiceVisual(icon?: string | null) {
  return icon ? SERVICE_VISUAL_BY_KEY[icon.trim().toLowerCase()] : undefined;
}

/** Merges a backend Product record with local visual fallbacks for anything the backend hasn't set yet. */
export function toProductMeta(product: Product): ProductMeta {
  const fallback = VISUAL_FALLBACK[product.key] ?? DEFAULT_VISUAL;

  return {
    key: product.key,
    label: product.label,
    tagline: product.tagline || fallback.tagline,
    gradient: fallback.gradient,
    color: product.color || undefined,
    Icon: (product.icon && ICON_BY_KEY[product.icon]) || fallback.Icon,
  };
}

export const CATEGORY_ICONS: Record<string, { gradient: string; Icon: LucideIcon }> = {
  banking:      { gradient: "from-blue-500 to-indigo-600", Icon: Landmark },
  "real estate": { gradient: "from-sky-400 to-blue-600",   Icon: Building2 },
  pricing:      { gradient: "from-teal-400 to-cyan-600",   Icon: BadgeDollarSign },
  "f&b":        { gradient: "from-orange-400 to-red-500",  Icon: Utensils },
};

export function getCategoryIcon(category?: string) {
  return CATEGORY_ICONS[category?.toLowerCase() ?? ""] ?? { gradient: "from-slate-400 to-slate-600", Icon: BarChart3 };
}

export interface GroupedService {
  service: Service;
  product: ProductKey;
  category: string;
  country: string;
}

/** Resolves a service's product-suite grouping from backend-supplied fields, or null when it doesn't belong to a product. */
export function resolveServiceGroup(service: Service): GroupedService | null {
  if (!service.product || !service.category || !service.country) return null;

  return {
    service,
    product: service.product,
    category: service.category,
    country: service.country,
  };
}

export function groupServicesByProduct(services: Service[]) {
  const grouped = new Map<ProductKey, GroupedService[]>();
  const other: Service[] = [];

  for (const service of services) {
    const group = resolveServiceGroup(service);
    if (!group) {
      other.push(service);
      continue;
    }
    const list = grouped.get(group.product) ?? [];
    list.push(group);
    grouped.set(group.product, list);
  }

  return { grouped, other };
}
