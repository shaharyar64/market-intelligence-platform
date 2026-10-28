import Sidebar from "@/components/layout/Sidebar";
import { SidebarProvider } from "@/components/layout/SidebarContext";

type DashboardShellProps = {
  children: React.ReactNode;
  dashboardType: string;
  userRole?: string;
};

/**
 * Keeps every product dashboard on the same responsive navigation contract.
 * On small screens Sidebar becomes an accessible drawer; on larger screens it
 * remains a fixed navigation rail while only the content area scrolls.
 */
export default function DashboardShell({
  children,
  dashboardType,
  userRole,
}: DashboardShellProps) {
  return (
    <SidebarProvider>
      <div className="flex h-dvh min-h-dvh overflow-hidden" style={{ background: "transparent" }}>
        <Sidebar dashboardType={dashboardType} userRole={userRole} />
        <main className="min-w-0 flex-1 overflow-y-auto" style={{ overflowX: "clip" }}>
          <div className="min-h-full">{children}</div>
        </main>
      </div>
    </SidebarProvider>
  );
}
