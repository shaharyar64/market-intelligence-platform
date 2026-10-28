"use client";

import type { ReactNode } from "react";
import Link from "next/link";
import { ArrowUpRight, RefreshCw } from "lucide-react";
import DashboardTopbar from "@/components/layout/DashboardTopbar";
import type { Resource } from "@/lib/useAsyncResource";
import s from "./campaign.module.css";

export { default as s } from "./campaign.module.css";
export const colors = {
  instagram: "#a65a88",
  linkedin: "#5879bb",
  tiktok: "#138577",
  twitter: "#697582",
};
export const compact = (value: number) =>
  new Intl.NumberFormat("en", {
    notation: "compact",
    maximumFractionDigits: 1,
  }).format(value);
export const number = (value: number) =>
  new Intl.NumberFormat("en", { maximumFractionDigits: 1 }).format(value);
export const platform = (value: string) =>
  ({
    twitter: "X",
    tiktok: "TikTok",
    linkedin: "LinkedIn",
    instagram: "Instagram",
    youtube: "YouTube",
  })[value] ?? value.charAt(0).toUpperCase() + value.slice(1);
export const delta = (value: number | null, suffix = "%") =>
  value == null
    ? "Not available"
    : `${value > 0 ? "+" : ""}${number(value)}${suffix}`;
export const axis = {
  axisLine: false,
  tickLine: false,
  tick: { fill: "var(--ceer-muted)", fontSize: 11 },
};
export const tooltip = {
  background: "var(--ceer-card)",
  border: "1px solid var(--ceer-line)",
  borderRadius: 10,
  color: "var(--ceer-ink)",
  fontSize: 12,
};

export function CampaignShell({
  title,
  description,
  children,
}: {
  title: string;
  description: string;
  children: ReactNode;
}) {
  return (
    <div className={s.root}>
      <DashboardTopbar title="CEER Launch Study" />
      <div className={s.workspace}>
        <header className={s.heading}>
          <div>
            <h1>{title}</h1>
            <p>{description}</p>
          </div>
          <span className={s.sourceBadge}><span /> Launch analysis</span>
        </header>
        {children}
      </div>
    </div>
  );
}

export function Panel({
  title,
  description,
  action,
  children,
}: {
  title: string;
  description: string;
  action?: ReactNode;
  children: ReactNode;
}) {
  return (
    <section className={s.panel}>
      <div className={s.panelHeading}>
        <div>
          <h2>{title}</h2>
          <p>{description}</p>
        </div>
        {action}
      </div>
      {children}
    </section>
  );
}

export function Load<T>({
  resource,
  children,
  empty,
}: {
  resource: Resource<T>;
  children: (data: T) => ReactNode;
  empty?: (data: T) => boolean;
}) {
  if (resource.loading)
    return (
      <div className={s.loading} role="status">
        <span className={s.skeleton} />
        <span className={s.skeleton} />
        <span className={s.skeleton} />
        <span>Loading launch-study data…</span>
      </div>
    );
  if (resource.error)
    return (
      <div className={s.loadError} role="alert">
        <p>{resource.error}</p>
        <button onClick={resource.reload}>
          <RefreshCw size={14} /> Retry data
        </button>
      </div>
    );
  if (
    resource.data === null ||
    (Array.isArray(resource.data) && !resource.data.length) ||
    empty?.(resource.data)
  )
    return (
      <div className={s.empty}>No records available for this selection.</div>
    );
  return <>{children(resource.data)}</>;
}

export function Note({ children }: { children: ReactNode }) {
  return <p className={s.note}>{children}</p>;
}
export function Chart({
  label,
  children,
}: {
  label: string;
  children: ReactNode;
}) {
  return (
    <div className={s.chart} role="img" aria-label={label}>
      {children}
    </div>
  );
}
export function MoreLink({
  href,
  children,
}: {
  href: string;
  children: ReactNode;
}) {
  return (
    <Link href={href} className={s.more}>
      {children}
      <ArrowUpRight size={16} />
    </Link>
  );
}
