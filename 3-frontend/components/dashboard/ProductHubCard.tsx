"use client";

import Link from "next/link";
import { motion } from "framer-motion";
import { ArrowRight, LucideIcon } from "lucide-react";

export default function ProductHubCard({
  href,
  label,
  tagline,
  gradient,
  color,
  Icon,
  count,
}: {
  href: string;
  label: string;
  tagline: string;
  gradient: string;
  color?: string;
  Icon: LucideIcon;
  count: number;
}) {
  return (
    <Link href={href} className="block h-full">
      <motion.div
        whileHover={{ y: -6, scale: 1.018 }}
        transition={{ type: "spring", stiffness: 200, damping: 20 }}
        className="group relative cursor-pointer h-full"
      >
        <div className="absolute -inset-px rounded-2xl opacity-0 group-hover:opacity-100 transition-opacity duration-500 blur-xl -z-10 bg-gradient-to-br from-violet-300/50 via-indigo-300/40 to-blue-300/50" />

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
          <div className="absolute top-0 left-5 right-5 h-px bg-gradient-to-r from-transparent via-white to-transparent rounded-full" />

          <div className="flex items-start justify-between">
            <div
              className={`h-11 w-11 rounded-xl flex items-center justify-center shadow-lg relative overflow-hidden ${color ? "" : `bg-gradient-to-br ${gradient}`}`}
              style={color ? { background: color } : undefined}
            >
              <div className="absolute inset-0 bg-white/20 rounded-xl" />
              <Icon className="h-5 w-5 text-white relative z-10 drop-shadow-sm" />
            </div>
            <span className="text-xs font-semibold text-violet-600 bg-violet-100 px-2.5 py-1 rounded-full">
              {count} {count === 1 ? "workspace" : "workspaces"}
            </span>
          </div>

          <h2 className="mt-3 text-lg font-bold tracking-tight text-slate-900">{label}</h2>
          <p className="mt-1 text-sm leading-relaxed text-slate-500 line-clamp-2">{tagline}</p>

          <div className="mt-auto pt-4 flex items-center justify-between">
            <span className="text-sm font-medium tracking-wide text-violet-600">
              View workspaces
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
    </Link>
  );
}
