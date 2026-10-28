"use client";

import React, { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { motion } from "framer-motion";
import { ShieldCheck } from "lucide-react";
import TopNavbar from "@/components/layout/TopNavbar";
import ProductHubCard from "@/components/dashboard/ProductHubCard";
import { getMe, getMyServices, getProducts } from "@/lib/user";
import type { Service, User } from "@/lib/user";
import { toProductMeta, groupServicesByProduct, type ProductMeta } from "@/lib/productGroups";

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

export default function DashboardsPage() {
  const router = useRouter();

  const [user, setUser] = useState<User | null>(null);
  const [services, setServices] = useState<Service[]>([]);
  const [products, setProducts] = useState<ProductMeta[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    async function loadData() {
      try {
        const [me, myServices, myProducts] = await Promise.all([getMe(), getMyServices(), getProducts()]);
        setUser(me);
        setServices(myServices);
        setProducts(
          myProducts
            .filter((p) => p.is_active !== false)
            .sort((a, b) => a.sort_order - b.sort_order)
            .map(toProductMeta)
        );
      } catch (err) {
        console.error("Auth error:", err);
        router.push("/login");
      } finally {
        setLoading(false);
      }
    }
    loadData();
  }, [router]);

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

  return (
    <div className="relative min-h-screen overflow-hidden bg-[#eef0f8]">
      <div className="pointer-events-none absolute inset-0 -z-10 overflow-hidden">
        <div className="absolute -top-40 -left-40 h-[650px] w-[650px] rounded-full bg-violet-200/60 blur-[130px]" />
        <div className="absolute -top-20 right-0 h-[450px] w-[550px] rounded-full bg-indigo-200/50 blur-[110px]" />
        <div className="absolute bottom-10 left-1/4 h-[400px] w-[600px] rounded-full bg-blue-200/40 blur-[120px]" />
        <div className="absolute bottom-0 right-1/4 h-[300px] w-[400px] rounded-full bg-purple-200/30 blur-[100px]" />
      </div>

      <TopNavbar />

      <main className="max-w-6xl mx-auto px-6 sm:px-10 pt-8 pb-10">
        <motion.div
          initial={{ opacity: 0, y: 18 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.5, ease: "easeOut" }}
        >
          <div className="inline-flex items-center gap-2 px-3.5 py-1.5 rounded-full bg-white/60 border border-violet-200/60 backdrop-blur-sm text-violet-700 text-xs font-semibold tracking-wide shadow-sm">
            <span className="h-1.5 w-1.5 rounded-full bg-violet-500 animate-pulse" />
            AI-Powered Intelligence
          </div>

          <h1 className="mt-3 text-2xl sm:text-3xl font-bold text-slate-900 leading-tight tracking-tight">
            Your intelligence{" "}
            <span
              className="bg-gradient-to-r from-violet-600 via-indigo-500 to-blue-600 bg-clip-text text-transparent"
              style={{ WebkitBackgroundClip: "text" }}
            >
              suite
            </span>
          </h1>

          <p className="mt-1.5 text-sm text-slate-500 max-w-xl leading-relaxed">
            Pick a product to see the markets and categories you have access to, {user?.full_name}.
          </p>

          {/* Admin button — only visible to admins */}
          {user?.role?.toUpperCase() === "ADMIN" && (
            <motion.div
              initial={{ opacity: 0, y: 10 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ delay: 0.3 }}
              className="mt-4"
            >
              <button
                onClick={() => router.push("/admin")}
                className="inline-flex items-center gap-2.5 px-5 py-2.5 rounded-xl text-sm font-semibold text-white shadow-lg transition-all hover:scale-105 hover:shadow-indigo-300/50"
                style={{ background: "linear-gradient(135deg, #6366f1, #8b5cf6)" }}
              >
                <ShieldCheck size={16} />
                Admin Panel
              </button>
            </motion.div>
          )}
        </motion.div>

        <motion.div
          variants={container}
          initial="hidden"
          animate="show"
          className="mt-6 grid grid-cols-1 sm:grid-cols-2 gap-4 items-stretch"
        >
          {products.map((product) => {
            const items = grouped.get(product.key) ?? [];
            if (items.length === 0) return null;
            return (
              <motion.div key={product.key} variants={cardVariant}>
                <ProductHubCard
                  href={`/products/${product.key}`}
                  label={product.label}
                  tagline={product.tagline}
                  gradient={product.gradient}
                  color={product.color}
                  Icon={product.Icon}
                  count={items.length}
                />
              </motion.div>
            );
          })}
        </motion.div>
      </main>
    </div>
  );
}
