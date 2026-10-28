import DashboardShell from "@/components/layout/DashboardShell";

export default function UaeBankBrandHealthLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return <DashboardShell dashboardType="uaeBankBrandHealth" userRole="ADMIN">{children}</DashboardShell>;
}
