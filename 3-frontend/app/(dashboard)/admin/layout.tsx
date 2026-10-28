import DashboardShell from "@/components/layout/DashboardShell";

export default function AdminLayout({ children }: { children: React.ReactNode }) {
  return <DashboardShell dashboardType="admin" userRole="ADMIN">{children}</DashboardShell>;
}
