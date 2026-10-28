import DashboardShell from "@/components/layout/DashboardShell";

export default function DataCollectionLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return <DashboardShell dashboardType="dataCollection" userRole="ADMIN">{children}</DashboardShell>;
}
