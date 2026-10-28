"use client";

import { createContext, useCallback, useContext, useEffect, useMemo, useState } from "react";
import { usePathname } from "next/navigation";

export const SIDEBAR_TRIGGER_ATTR = "data-sidebar-trigger";

type SidebarNav = {
  mobileOpen: boolean;
  open: () => void;
  close: () => void;
};

const SidebarNavContext = createContext<SidebarNav | null>(null);

export function useSidebarNav(): SidebarNav | null {
  return useContext(SidebarNavContext);
}

export function focusSidebarTrigger() {
  document.querySelector<HTMLElement>(`[${SIDEBAR_TRIGGER_ATTR}]`)?.focus();
}

export function SidebarProvider({ children }: { children: React.ReactNode }) {
  const pathname = usePathname();
  const [openedAt, setOpenedAt] = useState<string | null>(null);

  const mobileOpen = openedAt !== null && openedAt === pathname;

  const open = useCallback(() => setOpenedAt(pathname), [pathname]);
  const close = useCallback(() => setOpenedAt(null), []);

  useEffect(() => {
    if (!mobileOpen) return;
    const previous = document.body.style.overflow;
    document.body.style.overflow = "hidden";
    return () => { document.body.style.overflow = previous; };
  }, [mobileOpen]);

  const value = useMemo(() => ({ mobileOpen, open, close }), [mobileOpen, open, close]);

  return <SidebarNavContext.Provider value={value}>{children}</SidebarNavContext.Provider>;
}
