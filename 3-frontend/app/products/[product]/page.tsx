"use client";

import React, { useEffect, useState } from "react";
import { useRouter, useParams } from "next/navigation";
import Link from "next/link";
import { motion } from "framer-motion";
import { ArrowLeft } from "lucide-react";
import TopNavbar from "@/components/layout/TopNavbar";
import DashboardCard from "@/components/dashboard/DashboardCard";
import { getMe, getMyServices, getProducts } from "@/lib/user";
import type { Service } from "@/lib/user";
import { toProductMeta, getCategoryIcon, getServiceVisual, groupServicesByProduct, type ProductKey, type ProductMeta } from "@/lib/productGroups";

const container = {
  hidden: {},
  show: { transition: { staggerChildren: 0.09 } },
};

const cardVariant = {
  hidden: { opacity: 0, y: 28 },
  show: {
    opacity: 1,
    y: 0,
    transition: { type: "spring" as const, stiffness: 150, damping: 22 },
  },
};

export default function ProductDrilldownPage() {
  const router = useRouter();
  const params = useParams<{ product: string }>();
  const productKey = params.product as ProductKey;

  const [services, setServices] = useState<Service[]>([]);
  const [productMeta, setProductMeta] = useState<ProductMeta | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    async function loadData() {
      try {
        const [, myServices, myProducts] = await Promise.all([getMe(), getMyServices(), getProducts()]);
        setServices(myServices);
        const match = myProducts.find((p) => p.key === productKey);
        setProductMeta(match ? toProductMeta(match) : null);
      } catch (err) {
        console.error("Auth error:", err);
        router.push("/login");
      } finally {
        setLoading(false);
      }
    }
    loadData();
  }, [router, productKey]);

  if (loading) {
    return (
      <div className="min-h-screen flex items-center justify-center">
        <div className="flex items-center gap-3 text-slate-400 text-sm font-medium">
          <div className="h-4 w-4 rounded-full border-2 border-violet-400 border-t-transparent animate-spin" />
          Loading workspaces…
        </div>
      </div>
    );
  }

  const { grouped } = groupServicesByProduct(services);
  const items = grouped.get(productKey) ?? [];

  if (!productMeta) {
    return (
      <div className="min-h-screen flex items-center justify-center text-slate-500 text-sm">
        Unknown product.
      </div>
    );
  }

  const { label, tagline, gradient, color, Icon } = productMeta;

  return (
    <div className="relative min-h-screen overflow-hidden bg-[#eef0f8]">
      <div className="pointer-events-none absolute inset-0 -z-10 overflow-hidden">
        <div className="absolute -top-40 -left-40 h-[650px] w-[650px] rounded-full bg-violet-200/60 blur-[130px]" />
        <div className="absolute -top-20 right-0 h-[450px] w-[550px] rounded-full bg-indigo-200/50 blur-[110px]" />
      </div>

      <TopNavbar />

      <main className="max-w-6xl mx-auto px-6 sm:px-10 pt-8 pb-10">
        <Link
          href="/"
          className="inline-flex items-center gap-1.5 text-sm font-medium text-slate-500 hover:text-slate-700 transition-colors"
        >
          <ArrowLeft className="h-3.5 w-3.5" />
          All products
        </Link>

        <motion.div
          initial={{ opacity: 0, y: 12 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.4, ease: "easeOut" }}
          className="mt-3 flex items-center gap-4"
        >
          <div
            className={`h-11 w-11 rounded-xl flex items-center justify-center shadow-lg relative overflow-hidden flex-shrink-0 ${color ? "" : `bg-gradient-to-br ${gradient}`}`}
            style={color ? { background: color } : undefined}
          >
            <div className="absolute inset-0 bg-white/20 rounded-xl" />
            <Icon className="h-5 w-5 text-white relative z-10 drop-shadow-sm" />
          </div>
          <div>
            <h1 className="text-2xl font-bold text-slate-900 tracking-tight">{label}</h1>
            <p className="mt-0.5 text-sm text-slate-500">{tagline}</p>
          </div>
        </motion.div>

        <motion.div
          variants={container}
          initial="hidden"
          animate="show"
          className="mt-6 grid grid-cols-1 sm:grid-cols-2 gap-4 items-stretch"
        >
          {items.map((group) => {
            const { gradient: catGradient, Icon: CatIcon } = getCategoryIcon(group.category);
            const serviceVisual = getServiceVisual(group.service.icon);
            const ServiceIcon = serviceVisual?.Icon ?? CatIcon;
            const iconGradient = serviceVisual?.gradient ?? catGradient;
            const title = group.service.name || group.category;
            const description = group.service.description
              ? group.service.description
              : title !== group.category
                ? `${group.category} · ${group.country}`
                : group.country;
            return (
              <motion.div key={group.service.id} variants={cardVariant}>
                <DashboardCard
                  title={title}
                  description={description}
                  href={group.service.route || "#"}
                  icon={
                    <div className={`h-12 w-12 rounded-xl flex items-center justify-center shadow-lg bg-gradient-to-br ${iconGradient} relative overflow-hidden`}>
                      <div className="absolute inset-0 bg-white/20 rounded-xl" />
                      <ServiceIcon className="h-5 w-5 text-white relative z-10 drop-shadow-sm" />
                    </div>
                  }
                />
              </motion.div>
            );
          })}
        </motion.div>
      </main>
    </div>
  );
}
