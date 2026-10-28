import DashboardShell from "@/components/layout/DashboardShell";

export default function DigitalBrandHealthLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return <DashboardShell dashboardType="digitalBrandHealth" userRole="ADMIN">{children}</DashboardShell>;
}
