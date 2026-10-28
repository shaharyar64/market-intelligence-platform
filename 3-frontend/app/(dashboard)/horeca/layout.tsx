import DashboardShell from "@/components/layout/DashboardShell";

export default function HorecaLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return <DashboardShell dashboardType="horeca" userRole="ADMIN">{children}</DashboardShell>;
}
