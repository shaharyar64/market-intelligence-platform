"use client";

import Link from "next/link";
import { motion } from "framer-motion";
import { ArrowRight } from "lucide-react";

export default function DashboardCard({
  title,
  description,
  href,
  icon,
  disabled = false,
}: {
  title: string;
  description: string;
  href: string;
  icon: React.ReactNode;
  disabled?: boolean;
  featured?: boolean; // kept for API compat, unused visually
}) {
  const content = (
    <motion.div
      whileHover={!disabled ? { y: -6, scale: 1.018 } : {}}
      transition={{ type: "spring", stiffness: 200, damping: 20 }}
      className={`group relative h-full ${disabled ? "opacity-40 pointer-events-none" : "cursor-pointer"}`}
    >
      {/* Hover glow bleed */}
      {!disabled && (
        <div className="absolute -inset-px rounded-2xl opacity-0 group-hover:opacity-100 transition-opacity duration-500 blur-xl -z-10 bg-gradient-to-br from-violet-300/50 via-indigo-300/40 to-blue-300/50" />
      )}

      {/* Glass card surface */}
      <div
        className={[
          "relative h-full flex flex-col rounded-2xl p-5 overflow-hidden",
          "bg-white/50 backdrop-blur-xl",
          "border border-white/70",
          "shadow-[0_4px_24px_rgba(148,163,184,0.15),inset_0_1px_0_rgba(255,255,255,0.9)]",
          "group-hover:bg-white/65",
          "group-hover:border-white/90",
          "group-hover:shadow-[0_12px_40px_rgba(109,40,217,0.12),inset_0_1px_0_rgba(255,255,255,1)]",
          "transition-all duration-300",
        ].join(" ")}
      >
        {/* Shimmer top edge */}
        <div className="absolute top-0 left-5 right-5 h-px bg-gradient-to-r from-transparent via-white to-transparent rounded-full" />

        {/* Noise texture */}
        <div
          className="absolute inset-0 opacity-[0.025] pointer-events-none rounded-2xl"
          style={{
            backgroundImage: `url("data:image/svg+xml,%3Csvg viewBox='0 0 200 200' xmlns='http://www.w3.org/2000/svg'%3E%3Cfilter id='n'%3E%3CfeTurbulence type='fractalNoise' baseFrequency='0.85' numOctaves='4' stitchTiles='stitch'/%3E%3C/filter%3E%3Crect width='100%25' height='100%25' filter='url(%23n)'/%3E%3C/svg%3E")`,
          }}
        />

        {/* ICON */}
        <div className="mb-3 relative">{icon}</div>

        {/* TITLE */}
        <h3 className="text-[17px] font-semibold tracking-tight leading-snug text-slate-800">
          {title}
        </h3>

        {/* DESC */}
        <p className="mt-1 text-sm leading-relaxed text-slate-500 line-clamp-2">
          {description}
        </p>

        {/* CTA */}
        <div className="mt-auto pt-4 flex items-center justify-between">
          <span className="text-sm font-medium tracking-wide text-violet-600">
            Open Workspace
          </span>
          <motion.div
            className="h-7 w-7 rounded-full flex items-center justify-center bg-violet-100 group-hover:bg-gradient-to-br group-hover:from-violet-500 group-hover:to-indigo-600 transition-all duration-300"
            whileHover={{ x: 2 }}
            transition={{ type: "spring", stiffness: 400, damping: 25 }}
          >
            <ArrowRight className="h-3.5 w-3.5 text-violet-500 group-hover:text-white transition-colors duration-300" />
          </motion.div>
        </div>
      </div>
    </motion.div>
  );

  if (disabled) return content;
  return <Link href={href} className="block h-full">{content}</Link>;
}