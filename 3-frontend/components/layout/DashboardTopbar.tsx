"use client";

import { ReactNode, useEffect, useRef, useState } from "react";
import { useRouter } from "next/navigation";
import { CalendarClock, LogOut, Menu } from "lucide-react";
import ThemeToggle from "@/components/ui/ThemeToggle";
import InfoTooltip from "@/components/ui/InfoTooltip";
import { logoutUser } from "@/lib/authSession";
import { useSidebarNav, SIDEBAR_TRIGGER_ATTR } from "@/components/layout/SidebarContext";

function formatLastUpdated(value?: string | null) {
  if (!value) return "Waiting for data";

  const parsed = new Date(value);
  if (Number.isNaN(parsed.getTime())) return value;

  return parsed.toLocaleDateString("en-GB", {
    day: "2-digit",
    month: "short",
    year: "numeric",
  });
}

export default function DashboardTopbar({
  title,
  onLogout,
  accessory,
  lastUpdated,
  lastUpdatedLoading = false,
  lastUpdatedTooltip,
}: {
  title: string;
  onLogout?: () => Promise<void> | void;
  accessory?: ReactNode;
  lastUpdated?: string | null;
  lastUpdatedLoading?: boolean;
  lastUpdatedTooltip?: string;
}) {
  const router = useRouter();
  const [loading, setLoading] = useState(false);
  const [confirming, setConfirming] = useState(false);
  const logoutRef = useRef<HTMLDivElement>(null);
  const nav = useSidebarNav();

  useEffect(() => {
    if (!confirming) return;
    const onDown = (e: MouseEvent) => {
      if (!logoutRef.current?.contains(e.target as Node)) setConfirming(false);
    };
    const onKey = (e: KeyboardEvent) => { if (e.key === "Escape") setConfirming(false); };
    document.addEventListener("mousedown", onDown);
    document.addEventListener("keydown", onKey);
    return () => {
      document.removeEventListener("mousedown", onDown);
      document.removeEventListener("keydown", onKey);
    };
  }, [confirming]);

  const handleLogout = async () => {
    try {
      setLoading(true);
      setConfirming(false);
      if (onLogout) {
        await onLogout();
      }
      await logoutUser();
      router.push("/login");
    } catch (error) {
      console.error("Logout failed:", error);
      setLoading(false);
    }
  };

  return (
    <div
      style={{
        background: "var(--topbar-bg)",
        borderBottom: "1px solid var(--topbar-bd)",
        transition: "background 0.3s, border-color 0.3s",
      }}
      className="h-16 w-full flex items-center justify-between gap-3 px-6 sm:px-8 sticky top-0 z-30"
    >
      <div className="flex min-w-0 items-center gap-2">
        {nav && (
          <button
            {...{ [SIDEBAR_TRIGGER_ATTR]: "" }}
            onClick={nav.open}
            aria-label="Open navigation"
            aria-expanded={nav.mobileOpen}
            style={{ color: "var(--body-tx)", border: "1px solid var(--card-bd)" }}
            className="flex h-10 w-10 shrink-0 items-center justify-center rounded-xl transition-colors hover:text-[var(--accent-tx)] lg:hidden"
          >
            <Menu size={18} aria-hidden="true" />
          </button>
        )}
        <h1
          style={{ color: "var(--title-tx)" }}
          className="min-w-0 truncate text-lg font-semibold tracking-wide transition-colors duration-300"
        >
          {title}
        </h1>
      </div>

      {/* Right controls */}
      <div className="flex items-center gap-3 shrink-0">
        {accessory}

        {lastUpdated !== undefined && (
          <InfoTooltip content={lastUpdatedTooltip}>
          <div
            className="hidden sm:inline-flex h-10 items-center gap-2 rounded-full px-3 cursor-help"
            style={{
              background: "var(--card-bg)",
              border: "1px solid var(--card-bd)",
              backdropFilter: "var(--blur)",
              WebkitBackdropFilter: "var(--blur)",
              boxShadow: "var(--card-shadow)",
            }}
          >
            <div
              className="flex h-7 w-7 items-center justify-center rounded-full"
              style={{
                background: "var(--accent-soft)",
                border: "1px solid var(--accent-soft-bd)",
                color: "var(--accent-tx)",
              }}
            >
              <CalendarClock size={14} aria-hidden="true" />
            </div>
            <span className="text-sm font-bold" style={{ color: "var(--title-tx)" }}>
              {lastUpdatedLoading ? "Refreshing…" : formatLastUpdated(lastUpdated)}
            </span>
          </div>
          </InfoTooltip>
        )}

        {/* Theme toggle */}
        <ThemeToggle />

        <div ref={logoutRef} className="relative">
          <button
            onClick={() => setConfirming((c) => !c)}
            disabled={loading}
            aria-expanded={confirming}
            style={{
              color: loading ? "var(--muted-tx)" : "var(--body-tx)",
              background: "transparent",
              borderColor: "var(--card-bd)",
              transition: "color 0.2s, border-color 0.2s",
            }}
            className="flex items-center gap-2 px-4 py-2 rounded-full text-sm font-medium border transition-[color,border-color] duration-200 hover:text-red-500 hover:border-red-400"
          >
            <LogOut size={15} aria-hidden="true" />
            {loading ? "Logging out…" : "Logout"}
          </button>

          {confirming && !loading && (
            <div
              role="dialog"
              aria-label="Confirm logout"
              style={{
                background: "var(--dropdown-bg)",
                border: "1px solid var(--dropdown-bd)",
                boxShadow: "var(--card-shadow)",
              }}
              className="absolute right-0 top-full z-40 mt-2 w-56 rounded-xl p-3"
            >
              <p style={{ color: "var(--body-tx)" }} className="text-sm">
                Sign out of this account?
              </p>
              <div className="mt-3 flex justify-end gap-2">
                <button
                  onClick={() => setConfirming(false)}
                  style={{ border: "1px solid var(--card-bd)", color: "var(--body-tx)" }}
                  className="rounded-full px-3 py-1.5 text-xs font-semibold"
                >
                  Stay
                </button>
                <button
                  onClick={handleLogout}
                  autoFocus
                  className="rounded-full px-3 py-1.5 text-xs font-semibold"
                  style={{ background: "var(--fi-danger-tx)", color: "var(--dropdown-bg)" }}
                >
                  Log out
                </button>
              </div>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
