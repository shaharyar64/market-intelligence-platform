"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { dashboardNavigation } from "@/lib/navigation";
import Image from "next/image";
import { useEffect, useRef, useState } from "react";
import { X } from "lucide-react";
import { useSidebarNav, focusSidebarTrigger } from "@/components/layout/SidebarContext";

function CollapseIcon({ collapsed }: { collapsed: boolean }) {
  return (
    <svg
      width="16"
      height="16"
      viewBox="0 0 16 16"
      fill="none"
      xmlns="http://www.w3.org/2000/svg"
      aria-hidden="true"
      style={{ transition: "transform 0.25s ease", transform: collapsed ? "rotate(180deg)" : "rotate(0deg)" }}
    >
      <path
        d="M10 12L6 8L10 4"
        stroke="currentColor"
        strokeWidth="1.75"
        strokeLinecap="round"
        strokeLinejoin="round"
      />
    </svg>
  );
}

export default function Sidebar({
  dashboardType,
  userRole,
}: {
  dashboardType: string;
  userRole?: string;
}) {
  const pathname = usePathname();
  const navItems = dashboardNavigation[dashboardType] || [];
  const [collapsed, setCollapsed] = useState(false);
  const nav = useSidebarNav();
  const panelRef = useRef<HTMLElement>(null);

  const drawer = nav !== null;
  const drawerOpen = drawer && nav.mobileOpen;

  useEffect(() => {
    if (!drawerOpen) return;
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") {
        nav?.close();
        return;
      }

      if (e.key !== "Tab") return;

      const focusable = Array.from(
        panelRef.current?.querySelectorAll<HTMLElement>(
          'a[href], button:not([disabled]), input:not([disabled]), select:not([disabled]), textarea:not([disabled]), [tabindex]:not([tabindex="-1"])',
        ) ?? [],
      );
      if (focusable.length === 0) return;

      const first = focusable[0];
      const last = focusable[focusable.length - 1];
      if (e.shiftKey && document.activeElement === first) {
        e.preventDefault();
        last.focus();
      } else if (!e.shiftKey && document.activeElement === last) {
        e.preventDefault();
        first.focus();
      }
    };
    document.addEventListener("keydown", onKey);
    const first = panelRef.current?.querySelector<HTMLElement>("a, button");
    first?.focus();
    return () => {
      document.removeEventListener("keydown", onKey);
      focusSidebarTrigger();
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [drawerOpen]);

  const railCollapsed = collapsed && !drawerOpen;

  const aside = (
    <aside
      ref={panelRef}
      role={drawerOpen ? "dialog" : undefined}
      aria-modal={drawerOpen ? true : undefined}
      aria-label={drawerOpen ? "Navigation" : undefined}
      style={{
        background: "var(--sidebar-bg)",
        borderRight: "1px solid var(--sidebar-bd)",
        width: railCollapsed ? 64 : 256,
        overflow: "hidden",
        flexShrink: 0,
        transition: "background 0.3s, border-color 0.3s",
      }}
      className={
        drawer
          ? `fixed inset-y-0 left-0 z-50 flex h-full flex-col transition-transform duration-300 lg:static lg:z-auto lg:h-screen lg:translate-x-0 ${
              drawerOpen ? "visible translate-x-0 shadow-2xl" : "invisible -translate-x-full lg:visible"
            }`
          : "h-screen flex flex-col"
      }
    >
      {/* Brand */}
      <div
        style={{ borderBottom: "1px solid var(--sidebar-bd)", flexShrink: 0 }}
        className="h-16 flex items-center justify-between px-4"
      >
        {!railCollapsed && (
          <Link href="/" className="overflow-hidden rounded-lg">
            <Image
              src="/logo.svg"
              alt="Analytics Platform"
              width={182}
              height={32}
              className="sidebar-logo"
              style={{ minWidth: 120, width: "auto", height: "auto" }}
            />
          </Link>
        )}

        {drawer && (
          <button
            onClick={() => nav?.close()}
            aria-label="Close navigation"
            style={{ color: "var(--nav-inactive)", border: "1px solid var(--sidebar-bd)" }}
            className="flex h-9 w-9 shrink-0 items-center justify-center rounded-lg transition-colors hover:text-[var(--nav-hover-tx)] lg:hidden"
          >
            <X size={17} aria-hidden="true" />
          </button>
        )}

        <button
          onClick={() => setCollapsed((c) => !c)}
          aria-label={collapsed ? "Expand sidebar" : "Collapse sidebar"}
          aria-expanded={!collapsed}
          style={{
            display: "flex",
            alignItems: "center",
            justifyContent: "center",
            width: 28,
            height: 28,
            borderRadius: 8,
            border: "1px solid var(--sidebar-bd)",
            background: "transparent",
            color: "var(--nav-inactive)",
            cursor: "pointer",
            flexShrink: 0,
            marginLeft: railCollapsed ? "auto" : undefined,
            marginRight: railCollapsed ? "auto" : undefined,
            transition: "background 0.15s, color 0.15s",
          }}
          className={drawer ? "hidden lg:flex" : undefined}
          onMouseEnter={(e) => {
            (e.currentTarget as HTMLElement).style.background = "var(--nav-hover-bg)";
            (e.currentTarget as HTMLElement).style.color = "var(--nav-hover-tx)";
          }}
          onMouseLeave={(e) => {
            (e.currentTarget as HTMLElement).style.background = "transparent";
            (e.currentTarget as HTMLElement).style.color = "var(--nav-inactive)";
          }}
        >
          <CollapseIcon collapsed={collapsed} />
        </button>
      </div>

      {/* Navigation */}
      <nav
        aria-label={`${dashboardType} sections`}
        className="flex-1 py-4 space-y-0.5 overflow-y-auto overflow-x-hidden"
        style={{ padding: railCollapsed ? "16px 8px" : "16px 12px" }}
      >
        {navItems.map((item) => {
          if (item.roles && userRole && !item.roles.includes(userRole)) return null;

          const isActive = pathname === item.href;
          const Icon = item.icon;

          const baseColor = isActive
            ? { background: "var(--nav-active-bg)", color: "var(--nav-active-tx)" }
            : { color: "var(--nav-inactive)" };
          const linkStyle = railCollapsed
            ? { ...baseColor, justifyContent: "center", padding: "10px 0" }
            : { ...baseColor, gap: 12, padding: "9px 14px" };

          return (
            <Link
              key={item.label}
              href={item.href}
              title={railCollapsed ? item.label : undefined}
              aria-current={isActive ? "page" : undefined}
              style={linkStyle}
              className="flex items-center rounded-xl transition-colors duration-200"
              onMouseEnter={(e) => {
                if (!isActive) {
                  (e.currentTarget as HTMLElement).style.background = "var(--nav-hover-bg)";
                  (e.currentTarget as HTMLElement).style.color = "var(--nav-hover-tx)";
                }
              }}
              onMouseLeave={(e) => {
                if (!isActive) {
                  (e.currentTarget as HTMLElement).style.background = "transparent";
                  (e.currentTarget as HTMLElement).style.color = "var(--nav-inactive)";
                }
              }}
            >
              <Icon className="h-5 w-5 shrink-0" aria-hidden="true" />
              {!railCollapsed && <span className="text-sm font-medium truncate">{item.label}</span>}
              {!railCollapsed && isActive && (
                <div
                  aria-hidden="true"
                  className="ml-auto w-1.5 h-6 bg-gradient-to-b from-blue-500 to-cyan-500 rounded-full flex-shrink-0"
                />
              )}
            </Link>
          );
        })}
      </nav>
    </aside>
  );

  if (!drawer) return aside;

  return (
    <>
      <div
        onClick={() => nav?.close()}
        aria-hidden="true"
        className={`fixed inset-0 z-40 bg-slate-950/50 backdrop-blur-sm transition-opacity duration-300 lg:hidden ${
          drawerOpen ? "opacity-100" : "pointer-events-none opacity-0"
        }`}
      />
      {aside}
    </>
  );
}
